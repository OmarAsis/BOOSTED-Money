from datetime import timedelta
from db_control import get_connection


def previous_period_bounds(current_start, current_end):
    period_length = (current_end - current_start).days + 1  # +1 because both ends are inclusive

    prior_end = current_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=period_length - 1)

    return prior_start, prior_end


def _aggregate_by_category(conn, start_date, end_date):
    """
    sums EXPENSES only (amount < 0) per category within a date range. 
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT categories.name, SUM(transactions.amount)
        FROM transactions
        JOIN categories ON transactions.category_id = categories.id
        WHERE transactions.date >= ? AND transactions.date <= ?
          AND transactions.amount < 0
        GROUP BY categories.name
    """, (start_date, end_date))

    return {name: abs(total) for name, total in cursor.fetchall()}


def compare_periods(conn, current_start, current_end, prior_start, prior_end):
    """
    Returns per-category and overall % change in spend between
    two periods. Positive % = spending went UP vs the prior
    period, negative % = spending went DOWN.

    Returns a dict:
        {
            "categories": {
                "Food": {"current": 90.0, "prior": 60.0, "pct_change": 50.0},
                ...
            },
            "current_total": 105.99,
            "prior_total": 80.00,
            "overall_pct_change": 32.5,
        }

    A category with spend in the current period but NONE in the
    prior period gets pct_change = None (can't compute a % change
    from zero — "infinite increase" isn't a useful number to show).
    """
    current_totals = _aggregate_by_category(conn, current_start, current_end)
    prior_totals = _aggregate_by_category(conn, prior_start, prior_end)

    all_categories = set(current_totals.keys()) | set(prior_totals.keys())

    category_comparisons = {}
    for category in all_categories:
        current_amount = current_totals.get(category, 0.0)
        prior_amount = prior_totals.get(category, 0.0)

        if prior_amount == 0:
            pct_change = None
        else:
            pct_change = ((current_amount - prior_amount) / prior_amount) * 100

        category_comparisons[category] = {
            "current": current_amount,
            "prior": prior_amount,
            "pct_change": pct_change,
        }

    current_total = sum(current_totals.values())
    prior_total = sum(prior_totals.values())

    if prior_total == 0:
        overall_pct_change = None
    else:
        overall_pct_change = ((current_total - prior_total) / prior_total) * 100

    return {
        "categories": category_comparisons,
        "current_total": current_total,
        "prior_total": prior_total,
        "overall_pct_change": overall_pct_change,
    }


if __name__ == "__main__":
    from datetime import date

    conn = get_connection()

    current_start, current_end = date(2026, 8, 1), date(2026, 8, 14)
    prior_start, prior_end = previous_period_bounds(current_start, current_end)

    print(f"Current period: {current_start} to {current_end}")
    print(f"Prior period:   {prior_start} to {prior_end}")

    result = compare_periods(conn, str(current_start), str(current_end), str(prior_start), str(prior_end))
    print(result)
