from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# One shared Console object
console = Console()


def format_currency(amount):
    """Formats a number as a dollar string, e.g. -24.5 -> '-$24.50'"""
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def print_transactions_table(rows, title="Transactions"):
    """
    Prints transaction rows as a colored rich Table.
    Expects each row as: (id, date, description, amount, category)
    Expenses print in red, deposits in green.
    """
    if not rows:
        console.print("[dim]No transactions found.[/dim]")
        return

    table = Table(title=title, show_lines=False, header_style="bold cyan")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Date")
    table.add_column("Description")
    table.add_column("Amount", justify="right")
    table.add_column("Category")

    for txn_id, date, desc, amount, category in rows:
        desc = desc or "(none)"
        # Color the amount based on sign: red for expenses, green for deposits.
        amount_style = "red" if amount < 0 else "green"
        amount_text = Text(format_currency(amount), style=amount_style)
        table.add_row(str(txn_id), date, desc, amount_text, category)

    console.print(table)


STATUS_COLORS = {
    "under": "green",
    "at": "yellow",
    "over": "red",
    "no budget set": "dim",
}


def print_budget_status_table(budget_checks):
    """
    Prints a list of check_budget()/check_all_budgets() results as
    a color-coded table
    """
    if not budget_checks:
        console.print("[dim]No budgets set yet.[/dim]")
        return

    table = Table(title="Budget Status", header_style="bold cyan")
    table.add_column("Category")
    table.add_column("Spent", justify="right")
    table.add_column("Limit", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("% Used", justify="right")
    table.add_column("Status")

    for check in budget_checks:
        color = STATUS_COLORS.get(check["status"], "white")

        if check["status"] == "no budget set":
            table.add_row(
                check["category"], format_currency(check["spent"]),
                "—", "—", "—", Text("NO BUDGET", style=color)
            )
            continue

        table.add_row(
            check["category"],
            format_currency(check["spent"]),
            format_currency(check["limit"]),
            format_currency(check["remaining"]),
            f"{check['pct_used']:.0f}%",
            Text(check["status"].upper(), style=f"bold {color}"),
        )

    console.print(table)



def print_subscriptions_table(subscriptions):
    """
    Prints active recurring subscriptions.
    Expects rows as: (merchant, category, expected_amount, interval_days, next_date)
    """
    if not subscriptions:
        console.print("[dim]No active subscriptions detected.[/dim]")
        return

    table = Table(title="Active Subscriptions", header_style="bold cyan")
    table.add_column("Merchant")
    table.add_column("Category")
    table.add_column("Amount", justify="right")
    table.add_column("Every")
    table.add_column("Next Expected")

    interval_labels = {7: "week", 14: "2 weeks", 30: "month"}

    for merchant, category, amount, interval_days, next_date in subscriptions:
        label = interval_labels.get(interval_days, f"{interval_days} days")
        table.add_row(merchant.title(), category, format_currency(amount), label, next_date)

    console.print(table)


def format_trend_suffix(pct_change):
    """
    Returns a rich-markup string like " (up 12% vs last period)"
    in red (spending increased — bad) or " (down 8% vs last
    period)" in green (spending decreased — good).
    """
    if pct_change is None:
        return ""
    if pct_change > 0:
        return f" [red](up {pct_change:.0f}% vs last period)[/red]"
    elif pct_change < 0:
        return f" [green](down {abs(pct_change):.0f}% vs last period)[/green]"
    else:
        return " [dim](flat vs last period)[/dim]"


def print_report_header(start_date, end_date, total_spent, overall_pct_change=None):
    trend_suffix = format_trend_suffix(overall_pct_change)
    text = (f"[bold]{start_date}[/bold] to [bold]{end_date}[/bold]\n"
            f"Total spent: [bold]{format_currency(total_spent)}[/bold]{trend_suffix}")
    console.print(Panel(text, title="Spending Report", border_style="cyan"))


def print_top_expenditures(top_n):
    """Expects a list of (category, total) tuples, already sorted."""
    if not top_n:
        console.print("[dim]No expenditures to rank.[/dim]")
        return

    table = Table(title="Top Expenditures", header_style="bold cyan")
    table.add_column("Rank", justify="right")
    table.add_column("Category")
    table.add_column("Total", justify="right")

    for rank, (category, total) in enumerate(top_n, 1):
        table.add_row(str(rank), category, format_currency(total))

    console.print(table)


if __name__ == "__main__":
    sample_rows = [
        (1, "2026-08-13", "Sushi lunch", -24.0, "Food"),
        (2, "2026-08-14", "Paycheck", 1500.0, "Salary"),
    ]
    print_transactions_table(sample_rows)

    sample_budgets = [
        {"category": "Food", "spent": 90.0, "limit": 100.0, "remaining": 10.0, "pct_used": 90.0, "status": "under"},
        {"category": "Entertainment", "spent": 55.0, "limit": 50.0, "remaining": -5.0, "pct_used": 110.0, "status": "over"},
        {"category": "Rent", "spent": 0.0, "limit": None, "remaining": None, "pct_used": None, "status": "no budget set"},
    ]
    print_budget_status_table(sample_budgets)

    sample_subs = [("NETFLIX COM", "Entertainment", 15.99, 30, "2026-08-31")]
    print_subscriptions_table(sample_subs)

    print_report_header("2026-08-01", "2026-08-14", 192.59)
    print_top_expenditures([("Food", 99.50), ("Transport", 45.00)])
