from db_control import get_connection
from transactions import add_Transaction, edit_transaction, remove_transaction, get_transaction
from search import search_transactions
from budgets import set_budget, check_budget
from reports import build_report, render_report_rich, get_period_bounds
from csv_importer import import_csv
from recurring import detect_recurring, list_active_subscriptions, estimate_monthly_recurring_cost
from pdf_export import export_report_pdf
from goals import create_goal
from rich_display import (
    console, print_transactions_table, print_budget_status_table,
    print_subscriptions_table,
)


def show_menu():
    console.print("\n[bold cyan]===== Boosted Money =====[/bold cyan]")
    console.print("1. Add a transaction")
    console.print("2. Search transactions")
    console.print("3. Edit a transaction")
    console.print("4. Delete a transaction")
    console.print("5. Set a budget")
    console.print("6. Check a budget")
    console.print("7. View report (current biweekly period)")
    console.print("8. Import CSV bank statement")
    console.print("9. Detect / view subscriptions")
    console.print("10. Export report as PDF")
    console.print("11. Set a savings goal")
    console.print("12. Exit")


def handle_add():
    new_id = add_Transaction()
    console.print(f"\n[green]Saved! New transaction id: {new_id}[/green]")


def handle_search(conn):
    console.print("\n[dim]Leave any field blank to skip that filter.[/dim]")
    category = input("Category (or blank): ").strip() or None
    start_date = input("Start date YYYY-MM-DD (or blank): ").strip() or None
    end_date = input("End date YYYY-MM-DD (or blank): ").strip() or None
    keyword = input("Keyword in description (or blank): ").strip() or None

    results = search_transactions(conn, start_date=start_date, end_date=end_date,
                                   category=category, keyword=keyword)
    print_transactions_table(results)


def handle_edit(conn):
    txn_id = int(input("Enter the transaction ID to edit: "))
    existing = get_transaction(conn, txn_id)
    if existing is None:
        console.print(f"[red]No transaction found with id {txn_id}.[/red]")
        return

    console.print(f"Current values: {existing}")
    console.print("[dim]Leave any field blank to leave it unchanged.[/dim]")

    description = input("New description (or blank): ").strip() or None
    amount_input = input("New amount (or blank): ").strip()
    amount = float(amount_input) if amount_input else None
    category = input("New category (or blank): ").strip() or None
    date = input("New date YYYY-MM-DD (or blank): ").strip() or None

    success = edit_transaction(conn, txn_id, date=date, description=description,
                                amount=amount, category=category)
    if success:
        console.print(f"[green]Updated: {get_transaction(conn, txn_id)}[/green]")


def handle_delete(conn):
    txn_id = int(input("Enter the transaction ID to delete: "))
    existing = get_transaction(conn, txn_id)
    if existing is None:
        console.print(f"[red]No transaction found with id {txn_id}.[/red]")
        return

    confirm = input(f"Delete this transaction? {existing} (Y/N): ").strip()
    if confirm == "Y":
        remove_transaction(conn, txn_id)
        console.print("[green]Deleted.[/green]")
    else:
        console.print("Cancelled.")


def handle_set_budget(conn):
    category = input("Category: ").strip()
    amount = float(input("Budget amount: "))
    start_date = input("Period start date YYYY-MM-DD: ").strip()
    set_budget(conn, category, amount, start_date)
    console.print("[green]Budget set.[/green]")


def handle_check_budget(conn):
    category = input("Category: ").strip()
    start_date = input("Period start date YYYY-MM-DD: ").strip()
    end_date = input("Period end date YYYY-MM-DD: ").strip()
    result = check_budget(conn, category, start_date, end_date)
    print_budget_status_table([result])


def handle_report(conn):
    start, end = get_period_bounds()
    report = build_report(conn, str(start), str(end))
    render_report_rich(report)
    return report  # handed back so handle_export_pdf can reuse it without recomputing


def handle_import_csv(conn):
    path = input("Path to CSV file: ").strip()
    try:
        summary = import_csv(conn, path)
        console.print(
            f"[green]Imported {summary['rows_imported']} rows[/green], "
            f"skipped {summary['rows_skipped']} duplicates, "
            f"{summary['uncategorized_count']} landed in 'Other'."
        )
    except FileNotFoundError:
        console.print(f"[red]No file found at: {path}[/red]")


def handle_subscriptions(conn):
    console.print("Scanning transactions for recurring charges...")
    updated = detect_recurring(conn)
    console.print(f"[dim]Detected/updated {len(updated)} recurring series.[/dim]\n")

    subs = list_active_subscriptions(conn)
    print_subscriptions_table(subs)

    monthly_cost = estimate_monthly_recurring_cost(conn)
    console.print(f"\n[bold]Estimated monthly recurring cost:[/bold] ${monthly_cost:,.2f}")


def handle_export_pdf(conn):
    start, end = get_period_bounds()
    report = build_report(conn, str(start), str(end))

    default_path = f"reports/report_{start}_{end}.pdf"
    path_input = input(f"Save path (or blank for {default_path}): ").strip()
    output_path = path_input or default_path

    saved_path = export_report_pdf(report, output_path)
    console.print(f"[green]PDF saved to: {saved_path}[/green]")


def handle_set_goal(conn):
    name = input("Goal name (e.g. Emergency Fund): ").strip()
    target_amount = float(input("Target amount: "))
    target_date_input = input("Target date YYYY-MM-DD (or blank for no deadline): ").strip()
    target_date = target_date_input or None

    goal_id = create_goal(conn, name, target_amount, target_date)
    console.print(f"[green]Goal '{name}' created (id {goal_id}). "
                  f"It'll show up in your next report.[/green]")


def main():
    conn = get_connection()

    while True:
        show_menu()
        choice = input("Choose an option (1-12): ").strip()

        if choice == "1":
            handle_add()
        elif choice == "2":
            handle_search(conn)
        elif choice == "3":
            handle_edit(conn)
        elif choice == "4":
            handle_delete(conn)
        elif choice == "5":
            handle_set_budget(conn)
        elif choice == "6":
            handle_check_budget(conn)
        elif choice == "7":
            handle_report(conn)
        elif choice == "8":
            handle_import_csv(conn)
        elif choice == "9":
            handle_subscriptions(conn)
        elif choice == "10":
            handle_export_pdf(conn)
        elif choice == "11":
            handle_set_goal(conn)
        elif choice == "12":
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break
        else:
            console.print("[red]Please enter a number from 1-12.[/red]")


if __name__ == "__main__":
    main()
