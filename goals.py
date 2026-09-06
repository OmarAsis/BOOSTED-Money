# set a savings goal (e.g. "Emergency fund,
# $5000") and see how close they are to it. Progress is calculated fresh every time by summing
# net cash flow (income minus expenses) from the moment the goal
# was created up through "today"

from datetime import date
from db_control import get_connection


def create_goal(conn, name, target_amount, target_date=None):
    """Creates Goal and inserts it into goal table in database
        Return id of added row
    """
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO goals (name, target_amount, target_date, active)
        VALUES (?, ?, ?, 1)
    """, (name, target_amount, target_date))
    conn.commit()
    return cursor.lastrowid


def list_goals(conn, active_only=True):
    """Gets List of dicts about all goals, progress, and other variables stored in goal database

    Args:
        conn (conn): conn connects to goal table
        active_only (bool, optional): you may just to print currently active goals
    """
    cursor = conn.cursor()
    query = "SELECT id, name, target_amount, target_date, created_at, active FROM goals"
    if active_only:
        query += " WHERE active = 1"
    cursor.execute(query)
    
    return [
        {
            "id": row[0], "name": row[1], "target_amount": row[2],
            "target_date": row[3], "created_at": row[4], "active": bool(row[5]),
        }
        for row in cursor.fetchall()
    ]


def _saved_since(conn, since_date, as_of_date):
    """Calculates how much was saved from certain date to another
    by calculating net cash flow
    """
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(amount) FROM transactions
        WHERE date >= ? AND date <= ?
    """, (since_date, as_of_date))
    result = cursor.fetchone()[0]
    return result if result is not None else 0.0


def get_goal_progress(conn, goal, as_of_date):
    """
    Computes progress for a single goal (a dict as returned by
    list_goals()) as of a given date.
    """
    # created_at is stored as in SQLite's default timestamp format only the date portion (first 10
    # characters) matters for comparing against transaction dates.
    created_date = goal["created_at"][:10]

    saved = _saved_since(conn, created_date, as_of_date)
    target = goal["target_amount"]

    pct_complete = max(0.0, min(100.0, (saved / target * 100))) if target > 0 else 0.0
    remaining = target - saved

    days_left = None
    if goal["target_date"]:
        target_dt = date.fromisoformat(goal["target_date"])
        as_of_dt = date.fromisoformat(as_of_date)
        days_left = (target_dt - as_of_dt).days

    return {
        "name": goal["name"],
        "target_amount": target,
        "target_date": goal["target_date"],
        "saved": saved,
        "pct_complete": pct_complete,
        "remaining": remaining,
        "days_left": days_left,
    }


def get_all_goal_progress(conn, as_of_date):
    """IMPORTANT LIMITATION: this app tracks one pool of money (your
    transactions),If you have TWO goals both created on the same date, they'll both show
    progress based on the SAME underlying net savings.
    """
    goals = list_goals(conn, active_only=True)
    return [get_goal_progress(conn, goal, as_of_date) for goal in goals]


if __name__ == "__main__":
    conn = get_connection()

    goal_id = create_goal(conn, "Emergency Fund", 2000.00, target_date="2026-12-31")
    print(f"Created goal id: {goal_id}")

    progress = get_all_goal_progress(conn, "2026-08-14")
    for p in progress:
        print(p)