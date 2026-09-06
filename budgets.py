from db_control import get_connection
from transactions import get_category_id


def set_budget(conn, category, amount, start_date, period="biweekly"):
    
    '''
    Sets budgets: given obvious discernable variables and the insert papers
    '''
    
    category_id = get_category_id(conn, category)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO budgets (category_id, amount, period, start_date)
        VALUES (?, ?, ?, ?)
    """, (category_id, amount, period, start_date))

    conn.commit()
    return cursor.lastrowid


def get_period_spent(conn, category_id, start_date, end_date):
    """
    Gets how much was spent across budget period
    """
    
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SUM(amount) FROM transactions
        WHERE category_id = ? AND date >= ? AND date <= ? AND amount < 0
    """, (category_id, start_date, end_date))

    result = cursor.fetchone()[0]  # SUM() returns None if no rows matched
    total = result if result is not None else 0.0


    return abs(total) if total < 0 else 0.0


def check_budget(conn, category, start_date, end_date):
    
    """Checks category budgets returns dict that includes 
    pct_used, remaining, limit, spent, and a str describing whether you are in budget or not """
    
    category_id = get_category_id(conn, category)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT amount FROM budgets
        WHERE category_id = ? AND start_date <= ?
        ORDER BY start_date DESC
        LIMIT 1
    """, (category_id, start_date))

    row = cursor.fetchone()

    spent = get_period_spent(conn, category_id, start_date, end_date)

    if row is None:
        return {
            "category": category,
            "spent": spent,
            "limit": None,
            "remaining": None,
            "pct_used": None,
            "status": "no budget set",
        }

    limit = row[0]
    remaining = limit - spent
    pct_used = (spent / limit * 100) if limit > 0 else 0.0

    if spent < limit:
        status = "under"
    elif spent == limit:
        status = "at"
    else:
        status = "over"

    return {
        "category": category,
        "spent": spent,
        "limit": limit,
        "remaining": remaining,
        "pct_used": pct_used,
        "status": status,
    }



def check_all_budgets(conn, start_date, end_date):
    """Checks budget for all category budgets. Returns list of dicts that includes
    pct_used, remaining, limit, spent, and a str describing whether you are in budget or not """
    
    cursor = conn.cursor()

    cursor.execute("""
        SELECT categories.name, categories.id, budgets.amount
        FROM budgets
        JOIN categories ON budgets.category_id = categories.id
        WHERE budgets.start_date <= ?
        ORDER BY budgets.category_id, budgets.start_date DESC
    """, (start_date,))

    rows = cursor.fetchall()

    results = []
    seen = set()

    for name, category_id, limit in rows:

        if category_id in seen:
            continue

        seen.add(category_id)

        spent = get_period_spent(
            conn,
            category_id,
            start_date,
            end_date
        )

        remaining = limit - spent
        pct_used = spent / limit * 100 if limit > 0 else 0.0

        if spent < limit:
            status = "under"
        elif spent == limit:
            status = "at"
        else:
            status = "over"

        results.append({
            "category": name,
            "spent": spent,
            "limit": limit,
            "remaining": remaining,
            "pct_used": pct_used,
            "status": status
        })

    return results