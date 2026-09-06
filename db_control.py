import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "budget.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

CATEGORIES = ["Food", "Rent", "Utilities", "Transport", "Entertainment", "Salary", "Other"]
_conn = None


def get_connection():
    global _conn

    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        _conn = sqlite3.connect(DB_PATH)

        # SQLite has foreign key enforcement OFF by default.
        # Turn it ON so category_id must point to a real row.
        _conn.execute("PRAGMA foreign_keys = ON")

        init_db(_conn)

        seed_categories(_conn)

    return _conn


def init_db(conn):
    
    with open(SCHEMA_PATH, "r") as f:
        schema_text = f.read()

    conn.executescript(schema_text)
    conn.commit()


def seed_categories(conn):
    
    cursor = conn.cursor()

    for category_name in CATEGORIES:
        cursor.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            (category_name,)
        )

    conn.commit()
    
if __name__ == "__main__":
    conn = get_connection()
    print(f"Connected successfully. Database file is at: {DB_PATH}")

    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    print("Categories currently in the database:")
    for row in cursor.fetchall():
        print(f"  id={row[0]}  name={row[1]}")
