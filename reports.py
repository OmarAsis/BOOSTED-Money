from datetime import date, timedelta
from db_control import get_connection
from budgets import check_all_budgets
from format_output import format_currency, print_budget_status
from recurring import list_active_subscriptions
from trends import previous_period_bounds, compare_periods
from financial_sayings import get_financial_saying
from report_stats import (
    get_income_vs_expenses, get_transaction_stats,
    get_daily_average, get_projected_monthly_spend, find_biggest_movers,
    get_merchant_leaderboard, get_ytd_summary,
)
from goals import get_all_goal_progress


def get_period_bounds(reference_date=None):
    """
    Given any date, returns the start/end of the 14-day biweekly
    period it falls in: tethered to monthly calender wherer
    days 1-14 are one period, 15-end are the next.
    """
    if reference_date is None:
        reference_date = date.today()

    if reference_date.day <= 14:
        start = reference_date.replace(day=1)
        end = reference_date.replace(day=14)
    else:
        start = reference_date.replace(day=15)
        # Find the last day of this month by going to day 1 of
        # next month, then stepping back one day.
        if reference_date.month == 12:
            next_month = reference_date.replace(year=reference_date.year + 1, month=1, day=1)
        else:
            next_month = reference_date.replace(month=reference_date.month + 1, day=1)
        end = next_month - timedelta(days=1)

    return start, end


def aggregate_by_category(conn, start_date, end_date):
    """
    Sums spend per category within a date range.
    Returns a dict like {"Food": 140.0, "Entertainment": 15.0}
    Only counts expenses (negative amounts).
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

    totals = {}
    for name, total in cursor.fetchall():
        totals[name] = abs(total)

    return totals


def rank_top_categories(category_totals, n=5):
    """
    Pure function: takes an ALREADY-FETCHED {category: total} dict
    from aggregate_by_category and returns the top N,
    sorted highest-first. Does NOT touch the database.
    """
    # sorted() with key=lambda sorts by the second item in each
    # pair (the total), reverse=True means highest first.
    sorted_totals = sorted(category_totals.items(), key=lambda pair: pair[1], reverse=True)
    return sorted_totals[:n]


def top_expenditures(conn, start_date, end_date, n=5):
    """
    Returns the top N categories by total spend, descending.
    Returns a list of (category_name, total) tuples.
    """
    totals = aggregate_by_category(conn, start_date, end_date)
    return rank_top_categories(totals, n)


def build_report(conn, start_date, end_date):
    """
    Assembles the full report data as a dictionary.
    """
    category_totals = aggregate_by_category(conn, start_date, end_date)
    budget_statuses = check_all_budgets(conn, start_date, end_date)
    top_n = rank_top_categories(category_totals, n=5)
    subscriptions = list_active_subscriptions(conn)

    current_start_date = date.fromisoformat(start_date)
    current_end_date = date.fromisoformat(end_date)
    prior_start_date, prior_end_date = previous_period_bounds(current_start_date, current_end_date)

    trends = compare_periods(
        conn, start_date, end_date,
        str(prior_start_date), str(prior_end_date)
    )

    total_spent = sum(category_totals.values())

    income_vs_expenses = get_income_vs_expenses(conn, start_date, end_date)
    transaction_stats = get_transaction_stats(conn, start_date, end_date)
    daily_average = get_daily_average(total_spent, start_date, end_date)
    projected_monthly = get_projected_monthly_spend(daily_average)
    biggest_movers = find_biggest_movers(trends["categories"])

    merchant_leaderboard = get_merchant_leaderboard(conn, start_date, end_date, n=5)
    goal_progress = get_all_goal_progress(conn, end_date)
    ytd_summary = get_ytd_summary(conn, end_date)

    report_data = {
        "start_date": start_date,
        "end_date": end_date,
        "category_totals": category_totals,
        "budget_statuses": budget_statuses,
        "top_expenditures": top_n,
        "total_spent": total_spent,
        "subscriptions": subscriptions,
        "trends": trends,
        "income_vs_expenses": income_vs_expenses,
        "transaction_stats": transaction_stats,
        "daily_average": daily_average,
        "projected_monthly": projected_monthly,
        "biggest_movers": biggest_movers,
        "merchant_leaderboard": merchant_leaderboard,
        "goal_progress": goal_progress,
        "ytd_summary": ytd_summary,
    }

    report_data["saying"] = get_financial_saying(report_data)

    return report_data


def _print_trend_suffix_plain(pct_change):
    """
    Prints " (up 12% vs last period)" or similar, in plain text
    Prints percent_change
    """
    if pct_change is None:
        return
    direction = "up" if pct_change > 0 else "down" if pct_change < 0 else "flat"
    if direction == "flat":
        print(" (flat vs last period)", end="")
    else:
        print(f" ({direction} {abs(pct_change):.0f}% vs last period)", end="")


def _format_stats_lines(report_data):
    """
    Builds the plain-text lines for the "extra stats" section
    """
    lines = []

    iv = report_data["income_vs_expenses"]
    lines.append(f"Income: {format_currency(iv['income'])}  |  Expenses: {format_currency(iv['expenses'])}"
                 f"  |  Net: {format_currency(iv['net'])}")
    if iv["savings_rate"] is not None:
        lines.append(f"Savings rate: {iv['savings_rate']:.0f}% of income")

    ts = report_data["transaction_stats"]
    lines.append(f"Transactions this period: {ts['transaction_count']}"
                 f"  (avg {format_currency(ts['average_expense'])} per expense)")
    if ts["largest_expense"]:
        le = ts["largest_expense"]
        lines.append(f"Biggest single purchase: {le['description']} - "
                     f"{format_currency(le['amount'])} ({le['category']}, {le['date']})")

    lines.append(f"Daily average spend: {format_currency(report_data['daily_average'])}"
                 f"  |  Projected monthly pace: {format_currency(report_data['projected_monthly'])}")

    movers = report_data["biggest_movers"]
    if movers["biggest_increase"]:
        m = movers["biggest_increase"]
        lines.append(f"Biggest increase: {m['category']} up {m['pct_change']:.0f}% vs last period")
    if movers["biggest_decrease"]:
        m = movers["biggest_decrease"]
        lines.append(f"Biggest decrease: {m['category']} down {abs(m['pct_change']):.0f}% vs last period")

    return lines


def _format_merchant_leaderboard_lines(report_data):
    """Builds plain-text lines for the merchant leaderboard section."""
    leaderboard = report_data.get("merchant_leaderboard", [])
    if not leaderboard:
        return []

    lines = []
    for rank, entry in enumerate(leaderboard, 1):
        plural = "s" if entry["transaction_count"] != 1 else ""
        lines.append(f"{rank}. {entry['merchant'].title()}: {format_currency(entry['total'])} "
                     f"({entry['transaction_count']} charge{plural})")
    return lines


def _format_goal_progress_lines(report_data):
    """Builds plain-text lines for the savings goals section."""
    goals = report_data.get("goal_progress", [])
    if not goals:
        return []

    lines = []
    for g in goals:
        line = (f"{g['name']}: {format_currency(g['saved'])} of {format_currency(g['target_amount'])} "
                f"({g['pct_complete']:.0f}%)")
        if g["days_left"] is not None:
            line += f" - {g['days_left']} days left" if g["days_left"] >= 0 else " - past target date"
        lines.append(line)
    return lines


def _format_ytd_lines(report_data):
    """Builds plain-text lines for the year-to-date summary section."""
    ytd = report_data.get("ytd_summary")
    if not ytd:
        return []

    return [
        f"{ytd['year']} so far - Spent: {format_currency(ytd['total_spent_ytd'])}  |  "
        f"Income: {format_currency(ytd['total_income_ytd'])}  |  Net: {format_currency(ytd['net_ytd'])}",
        f"Average pace: {format_currency(ytd['avg_per_period'])} per biweekly period",
    ]


def render_report_terminal(report_data):
    """
    Prints the report data as readable terminal output.
    """
    print(f"\n=== Spending Report: {report_data['start_date']} to {report_data['end_date']} ===\n")

    print(f"Total spent: {format_currency(report_data['total_spent'])}", end="")
    _print_trend_suffix_plain(report_data["trends"]["overall_pct_change"])
    print()

    if report_data.get("saying"):
        print(f'"{report_data["saying"]}"\n')

    print("-- Overview --")
    for line in _format_stats_lines(report_data):
        print(f"  {line}")

    goal_lines = _format_goal_progress_lines(report_data)
    if goal_lines:
        print("\n-- Savings Goals --")
        for line in goal_lines:
            print(f"  {line}")

    merchant_lines = _format_merchant_leaderboard_lines(report_data)
    if merchant_lines:
        print("\n-- Top Merchants --")
        for line in merchant_lines:
            print(f"  {line}")

    print("\n-- Year to Date --")
    for line in _format_ytd_lines(report_data):
        print(f"  {line}")

    print("\n-- Spend by Category --")
    if not report_data["category_totals"]:
        print("No spending recorded this period.")
    else:
        category_trends = report_data["trends"]["categories"]
        for category, total in report_data["category_totals"].items():
            trend = category_trends.get(category, {})
            print(f"  {category}: {format_currency(total)}", end="")
            _print_trend_suffix_plain(trend.get("pct_change"))
            print()

    print("\n-- Top Expenditures --")
    if not report_data["top_expenditures"]:
        print("No expenditures to rank.")
    else:
        for rank, (category, total) in enumerate(report_data["top_expenditures"], 1):
            print(f"  {rank}. {category}: {format_currency(total)}")

    print("\n-- Budget Status --")
    if not report_data["budget_statuses"]:
        print("No budgets set.")
    else:
        for check in report_data["budget_statuses"]:
            print_budget_status(check)

    print()


def render_report_rich(report_data):
    """
    Same report data as render_report_terminal(), but rendered
    with colorful rich tables/panels instead of plain print().
    """
    
    from rich_display import (
        print_report_header, print_transactions_table,
        print_budget_status_table, print_top_expenditures,
        print_subscriptions_table, console,
    )

    print_report_header(
        report_data["start_date"], report_data["end_date"],
        report_data["total_spent"], report_data["trends"]["overall_pct_change"]
    )

    if report_data.get("saying"):
        console.print(f'[italic dim]"{report_data["saying"]}"[/italic dim]\n')

    console.print("[bold cyan]Overview[/bold cyan]")
    for line in _format_stats_lines(report_data):
        console.print(f"  {line}")
    console.print()

    goal_lines = _format_goal_progress_lines(report_data)
    if goal_lines:
        console.print("[bold cyan]Savings Goals[/bold cyan]")
        for line in goal_lines:
            console.print(f"  {line}")
        console.print()

    merchant_lines = _format_merchant_leaderboard_lines(report_data)
    if merchant_lines:
        console.print("[bold cyan]Top Merchants[/bold cyan]")
        for line in merchant_lines:
            console.print(f"  {line}")
        console.print()

    console.print("[bold cyan]Year to Date[/bold cyan]")
    for line in _format_ytd_lines(report_data):
        console.print(f"  {line}")
    console.print()

    console.print("\n[bold cyan]Spend by Category[/bold cyan]")
    if not report_data["category_totals"]:
        console.print("[dim]No spending recorded this period.[/dim]")
    else:
        from rich_display import format_trend_suffix
        category_trends = report_data["trends"]["categories"]
        for category, total in report_data["category_totals"].items():
            trend = category_trends.get(category, {})
            trend_suffix = format_trend_suffix(trend.get("pct_change"))
            console.print(f"  {category}: {format_currency(total)}{trend_suffix}")

    console.print()
    print_top_expenditures(report_data["top_expenditures"])

    console.print()
    print_budget_status_table(report_data["budget_statuses"])

    if report_data.get("subscriptions"):
        console.print()
        print_subscriptions_table(report_data["subscriptions"])



if __name__ == "__main__":
    conn = get_connection()
    start, end = "2026-08-01", "2026-08-14"
    report = build_report(conn, start, end)
    render_report_terminal(report)
