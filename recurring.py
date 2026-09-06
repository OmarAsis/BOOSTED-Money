#A "recurring" charge is one where the SAME merchant charges a SIMILAR amount at a roughly
# CONSISTENT interval (weekly/biweekly/monthly).

import re
from datetime import datetime, timedelta
from statistics import mean, pstdev
from db_control import get_connection


def normalize_merchant(description):
    """
    Strips trailing store numbers, transaction codes, and extra
    punctuation so the same merchant matches across statements.
         "NETFLIX.COM #4471"   -> "NETFLIX COM"
         "UBER EATS 8492"      -> "UBER EATS"
         "Shell Gas Station 22" -> "SHELL GAS STATION"
    """
    if not description:
        return ""

    text = description.upper()

    text = re.sub(r"#\d+", "", text)
    text = re.sub(r"\d{3,}", "", text)

    text = re.sub(r"[.\-*/]", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


def _interval_label(avg_days):
    if 5 <= avg_days <= 9:
        return "weekly", 7
    elif 12 <= avg_days <= 16:
        return "biweekly", 14
    elif 27 <= avg_days <= 33:
        return "monthly", 30
    else:
        return None, None

def detect_recurring(conn, min_occurrences=3, amount_tolerance_pct=0.10):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, date, description, amount, category_id
        FROM transactions
        WHERE amount < 0
        ORDER BY date
    """)
    all_expenses = cursor.fetchall()

    groups = {}
    for txn_id, date, description, amount, category_id in all_expenses:
        merchant = normalize_merchant(description)
        if not merchant:
            continue
        groups.setdefault(merchant, []).append({
            "id": txn_id, "date": date, "amount": amount, "category_id": category_id,
        })

    updated_series = []

    for merchant, txns in groups.items():
        if len(txns) < min_occurrences:
            continue  

        amounts = [abs(t["amount"]) for t in txns]
        avg_amount = mean(amounts)

        if avg_amount == 0:
            continue
        max_deviation = max(abs(a - avg_amount) for a in amounts) / avg_amount
        if max_deviation > amount_tolerance_pct:
            continue

        dates = sorted(datetime.strptime(t["date"], "%Y-%m-%d") for t in txns)
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]

        if not gaps:
            continue

        avg_gap = mean(gaps)
        period_label, interval_days = _interval_label(avg_gap)

        if period_label is None:
            continue 

        last_date = dates[-1].strftime("%Y-%m-%d")
        next_expected = (dates[-1] + timedelta(days=interval_days)).strftime("%Y-%m-%d")
        category_id = txns[-1]["category_id"]  # use most recent charge's category

        
        cursor.execute("SELECT id FROM recurring_series WHERE merchant_pattern = ?", (merchant,))
        existing = cursor.fetchone()

        if existing:
            series_id = existing[0]
            cursor.execute("""
                UPDATE recurring_series
                SET category_id = ?, expected_amount = ?, interval_days = ?,
                    last_date = ?, next_expected_date = ?, active = 1
                WHERE id = ?
            """, (category_id, avg_amount, interval_days, last_date, next_expected, series_id))
        else:
            cursor.execute("""
                INSERT INTO recurring_series
                    (merchant_pattern, category_id, expected_amount, interval_days,
                     last_date, next_expected_date, active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (merchant, category_id, avg_amount, interval_days, last_date, next_expected))
            series_id = cursor.lastrowid

        txn_ids = [t["id"] for t in txns]
        placeholders = ",".join("?" for _ in txn_ids)
        cursor.execute(
            f"UPDATE transactions SET recurring_series_id = ? WHERE id IN ({placeholders})",
            (series_id, *txn_ids)
        )

        updated_series.append({
            "merchant": merchant, "interval": period_label,
            "expected_amount": avg_amount, "occurrences": len(txns),
        })

    conn.commit()
    return updated_series


def list_active_subscriptions(conn):
    """
    Returns currently active recurring series with their expected
    amount, category name, and next expected charge date.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT recurring_series.merchant_pattern, categories.name,
               recurring_series.expected_amount, recurring_series.interval_days,
               recurring_series.next_expected_date
        FROM recurring_series
        JOIN categories ON recurring_series.category_id = categories.id
        WHERE recurring_series.active = 1
        ORDER BY recurring_series.expected_amount DESC
    """)
    return cursor.fetchall()


def estimate_monthly_recurring_cost(conn):
    """
    Normalizes every active recurring series to a monthly-equivalent
    cost and sums them. Weekly charges are scaled up (~4.33x),
    biweekly charges scaled up (~2.17x), monthly charges as-is.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT expected_amount, interval_days
        FROM recurring_series
        WHERE active = 1
    """)

    total = 0.0
    for amount, interval_days in cursor.fetchall():
        if interval_days == 7:
            total += amount * 4.33   # 4.33 weeks per month
        elif interval_days == 14:
            total += amount * 2.17   # 2.17 biweekly periods per month
        else:
            total += amount          # already monthly (or close enough)

    return total



if __name__ == "__main__":
    conn = get_connection()
    updated = detect_recurring(conn)
    print(f"Detected/updated {len(updated)} recurring series:")
    for series in updated:
        print(f"  {series['merchant']} — {series['interval']}, ~${series['expected_amount']:.2f}, "
              f"seen {series['occurrences']}x")

    print(f"\nEstimated monthly recurring cost: ${estimate_monthly_recurring_cost(conn):.2f}")





































    """
    Scans ALL transactions, groups by normalized merchant name,
    and flags groups where:
      - the merchant appears at least `min_occurrences` times
      - the amounts are consistent within `amount_tolerance_pct`
      - the gaps between charges cluster around a known interval

    Upserts matches into recurring_series and tags the matching
    transactions with recurring_series_id.
    Returns the list of series that were created or updated.
    """