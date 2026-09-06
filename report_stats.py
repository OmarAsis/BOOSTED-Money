from datetime import date
from recurring import normalize_merchant


def get_income_vs_expenses(conn, start_date, end_date):
    #DOCSTRINGS ON BOTTOM TRY THO PLZ
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) AS expenses
        FROM transactions
        WHERE date >= ? AND date <= ?
    """, (start_date, end_date))

    row = cursor.fetchone()
    income = float(row[0]) if row[0] is not None else 0.0
    expenses = abs(float(row[1])) if row[1] is not None else 0.0  # stored negative, flip for display

    net = income - expenses


    savings_rate = (net / income * 100) if income > 0 else None

    return {
        "income": income,
        "expenses": expenses,
        "net": net,
        "savings_rate": savings_rate,
    }


def get_transaction_stats(conn, start_date, end_date):
    """Return transaction count, average expense, and largest expense for a date range."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*), AVG(amount)
        FROM transactions
        WHERE date >= ? AND date <= ? AND amount < 0
    """, (start_date, end_date))
    count_row = cursor.fetchone()
    transaction_count = count_row[0] or 0
    average_expense = abs(count_row[1]) if count_row[1] is not None else 0.0

    cursor.execute("""
        SELECT transactions.description, transactions.date,
               transactions.amount, categories.name
        FROM transactions
        JOIN categories ON transactions.category_id = categories.id
        WHERE transactions.date >= ? AND transactions.date <= ?
          AND transactions.amount < 0
        ORDER BY transactions.amount ASC
        LIMIT 1
    """, (start_date, end_date))
    largest_row = cursor.fetchone()

    if largest_row:
        largest_expense = {
            "description": largest_row[0] or "(no description)",
            "date": largest_row[1],
            "amount": abs(largest_row[2]),
            "category": largest_row[3],
        }
    else:
        largest_expense = None

    return {
        "transaction_count": transaction_count,
        "average_expense": average_expense,
        "largest_expense": largest_expense,
    }


def get_daily_average(total_spent, start_date, end_date):
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days_in_period = (end - start).days + 1  # +1 because both ends are inclusive

    if days_in_period <= 0:
        return 0.0

    return total_spent / days_in_period


def get_projected_monthly_spend(daily_average):
    return daily_average * 30


def find_biggest_movers(category_trends):
    """
    Takes the "categories" dict and picks out the single
    biggest INCREASE and single biggest DECREASE.
    """
    # Only consider categories where we actually have a % change
    # to compare (i.e. they had spending in the prior period too).
    comparable = {
        name: data for name, data in category_trends.items()
        if data["pct_change"] is not None
    }

    if not comparable:
        return {"biggest_increase": None, "biggest_decrease": None}

    increases = {name: data for name, data in comparable.items() if data["pct_change"] > 0}
    decreases = {name: data for name, data in comparable.items() if data["pct_change"] < 0}

    biggest_increase = None
    if increases:
        name = max(increases, key=lambda n: increases[n]["pct_change"])
        biggest_increase = {"category": name, **increases[name]}

    biggest_decrease = None
    if decreases:
        # Most negative pct_change = biggest decrease.
        name = min(decreases, key=lambda n: decreases[n]["pct_change"])
        biggest_decrease = {"category": name, **decreases[name]}

    return {"biggest_increase": biggest_increase, "biggest_decrease": biggest_decrease}


def get_merchant_leaderboard(conn, start_date, end_date, n=5):
    """Return the top merchants by total spending in a date range."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT description, amount FROM transactions
        WHERE date >= ? AND date <= ? AND amount < 0
    """, (start_date, end_date))

    merchant_totals = {}
    merchant_counts = {}
    for description, amount in cursor.fetchall():
        merchant = normalize_merchant(description)
        if not merchant:
            merchant = "(no description)"
        merchant_totals[merchant] = merchant_totals.get(merchant, 0.0) + abs(amount)
        merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1

    leaderboard = [
        {"merchant": name, "total": total, "transaction_count": merchant_counts[name]}
        for name, total in merchant_totals.items()
    ]
    leaderboard.sort(key=lambda entry: entry["total"], reverse=True)

    return leaderboard[:n]


def get_ytd_summary(conn, as_of_date):
    """Return year-to-date income, spending, net savings, and average biweekly spending."""
    year = date.fromisoformat(as_of_date).year
    jan_first = f"{year}-01-01"

    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) AS expenses
        FROM transactions
        WHERE date >= ? AND date <= ?
    """, (jan_first, as_of_date))

    row = cursor.fetchone()
    income_ytd = float(row[0]) if row[0] is not None else 0.0
    expenses_ytd = abs(float(row[1])) if row[1] is not None else 0.0

    days_elapsed = (date.fromisoformat(as_of_date) - date.fromisoformat(jan_first)).days + 1
    periods_elapsed = days_elapsed / 14  # a rate, not a whole-number count — see docstring

    avg_per_period = expenses_ytd / periods_elapsed if periods_elapsed > 0 else 0.0

    return {
        "year": year,
        "total_spent_ytd": expenses_ytd,
        "total_income_ytd": income_ytd,
        "net_ytd": income_ytd - expenses_ytd,
        "avg_per_period": avg_per_period,
    }


if __name__ == "__main__":
    from db_control import get_connection

    conn = get_connection()
    start, end = "2026-08-01", "2026-08-14"

    print("Income vs Expenses:", get_income_vs_expenses(conn, start, end))
    print("Transaction stats:", get_transaction_stats(conn, start, end))

    daily_avg = get_daily_average(100.0, start, end)
    print(f"Daily average (on $100 total): ${daily_avg:.2f}")
    print(f"Projected monthly: ${get_projected_monthly_spend(daily_avg):.2f}")

    print("Merchant leaderboard:", get_merchant_leaderboard(conn, start, end))
    print("YTD summary:", get_ytd_summary(conn, end))