from db_control import get_connection


def search_transactions(conn, start_date=None, end_date=None, category=None, keyword=None):
    
    cursor = conn.cursor()
    query = """
        SELECT transactions.id, transactions.date, transactions.description,
               transactions.amount, categories.name
        FROM transactions
        JOIN categories ON transactions.category_id = categories.id
        WHERE 1=1
    """
    params = []

    if start_date is not None:
        query += " AND transactions.date >= ?"
        params.append(start_date)

    if end_date is not None:
        query += " AND transactions.date <= ?"
        params.append(end_date)

    if category is not None:
        query += " AND categories.name = ?"
        params.append(category)

    if keyword is not None:
        query += " AND LOWER(transactions.description) LIKE ?"
        params.append(f"%{keyword.lower()}%")

    # Sort most recent first, purely for readability.
    query += " ORDER BY transactions.date DESC"

    # params is a list — execute() wants a tuple, so we convert it.
    cursor.execute(query, tuple(params))

    return cursor.fetchall()


def print_results(rows):
    """Small helper to print search results in a readable table."""
    if not rows:
        print("No matching transactions found.")
        return

    print(f'{"ID":<4} {"Date":<12} {"Description":<20} {"Amount":<10} {"Category"}')
    for row in rows:
        txn_id, date, desc, amount, category = row
        desc = desc or "(none)"
        print(f"{txn_id:<4} {date:<12} {desc:<20} {amount:<10} {category}")


if __name__ == "__main__":
    conn = get_connection()

    print("=== All Food transactions ===")
    results = search_transactions(conn, category="Food")
    print_results(results)

    print("\n=== Food transactions in August 1-10 (COMBINED filters) ===")
    results = search_transactions(conn, category="Food", start_date="2026-08-01", end_date="2026-08-10")
    print_results(results)

    print("\n=== Keyword search: 'netflix' ===")
    results = search_transactions(conn, keyword="netflix")
    print_results(results)

    print("\n=== No filters at all — everything ===")
    results = search_transactions(conn)
    print_results(results)
