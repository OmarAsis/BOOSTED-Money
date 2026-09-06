def format_currency(amount):
    """
    Formats a number as a dollar string, e.g. -24.5 -> "-$24.50"
    """
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"

def print_transactions_table(rows):
    """
    Prints a list of transaction rows in a lined-up table.
    """
    if not rows:
        print("No transactions found.")
        return

    print(f'{"ID":<4} {"Date":<12} {"Description":<20} {"Amount":<12} {"Category"}')
    print("-" * 60)
    for row in rows:
        txn_id, date, desc, amount, category = row
        desc = desc or "(none)"
        print(f"{txn_id:<4} {date:<12} {desc:<20} {format_currency(amount):<12} {category}")


def print_budget_status(budget_check):
    """
    Prints a single check_budget() result in a readable line
    """
    status_markers = {
        "under": "[OK]",
        "at": "[AT LIMIT]",
        "over": "[OVER]",
        "no budget set": "[NO BUDGET]",
    }
    marker = status_markers.get(budget_check["status"], "")

    if budget_check["status"] == "no budget set":
        print(f"{marker} {budget_check['category']}: {format_currency(budget_check['spent'])} spent, no budget set")
        return

    print(
        f"{marker} {budget_check['category']}: "
        f"{format_currency(budget_check['spent'])} of {format_currency(budget_check['limit'])} "
        f"({budget_check['pct_used']:.0f}% used, {format_currency(budget_check['remaining'])} remaining)"
    )


def print_all_budget_statuses(budget_checks):
    """Prints a list of check_budget() results, one per line."""
    if not budget_checks:
        print("No budgets set yet.")
        return
    for check in budget_checks:
        print_budget_status(check)

if __name__ == "__main__":
    print(format_currency(-24.5))
    print(format_currency(1500))
    print(format_currency(0))

    sample_rows = [
        (1, "2026-08-13", "Sushi lunch", -24.0, "Food"),
        (2, "2026-08-14", "Paycheck", 1500.0, "Salary"),
    ]
    print_transactions_table(sample_rows)

    sample_budget = {
        "category": "Food", "spent": 90.0, "limit": 100.0,
        "remaining": 10.0, "pct_used": 90.0, "status": "under"
    }
    print_budget_status(sample_budget)
