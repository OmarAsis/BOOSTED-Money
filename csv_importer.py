import hashlib
import pandas as pd
from db_control import get_connection


"""IMPORTANT THAT IN KEYWORD_RULES DESCRIPTIVE WORDS ARE PUT BEFORE THE BIG"""

KEYWORD_RULES = {
    # ---- FOOD: restaurants, fast food, cafes ----
    "cheesecake factory": "Food", "chipotle": "Food", "mcdonald": "Food",
    "starbucks": "Food", "panera": "Food", "subway": "Food",
    "domino": "Food", "pizza hut": "Food", "taco bell": "Food",
    "wendy": "Food", "chick-fil-a": "Food", "chickfila": "Food",
    "olive garden": "Food", "applebee": "Food", "ihop": "Food",
    "denny's": "Food", "dunkin": "Food", "popeyes": "Food", "kfc": "Food",
    "in-n-out": "Food", "five guys": "Food", "shake shack": "Food",
    "panda express": "Food", "buffalo wild wings": "Food",
    "cracker barrel": "Food", "texas roadhouse": "Food", "chili's": "Food",
    "outback steakhouse": "Food", "red lobster": "Food",
    # ---- FOOD: grocery stores ----
    "whole foods": "Food", "trader joe": "Food", "safeway": "Food",
    "kroger": "Food", "publix": "Food", "albertsons": "Food",
    "costco wholesale": "Food", "aldi": "Food", "sprouts": "Food",
    "wegmans": "Food", "harris teeter": "Food", "food lion": "Food",
    "vons": "Food", "ralphs": "Food", "giant food": "Food",
    # ---- FOOD: delivery apps ----
    "uber eats": "Food", "doordash": "Food", "grubhub": "Food",
    "postmates": "Food", "instacart": "Food",
    # ---- FOOD: generic fallback ----
    "grocery": "Food", "restaurant": "Food", "cafe": "Food",
    "bakery": "Food", "diner": "Food", "bistro": "Food",

    # ---- TRANSPORT: rideshare, gas, airlines, car rental ----
    "uber": "Transport", "lyft": "Transport",
    "shell oil": "Transport", "chevron": "Transport", "exxon": "Transport",
    "mobil gas": "Transport", "bp gas": "Transport", "arco": "Transport",
    "delta air": "Transport", "united airlines": "Transport",
    "american airlines": "Transport", "southwest air": "Transport",
    "jetblue": "Transport", "spirit airlines": "Transport",
    "enterprise rent": "Transport", "hertz": "Transport", "avis": "Transport",
    "budget rent": "Transport", "national car rental": "Transport",
    "alamo rent": "Transport", "zipcar": "Transport", "turo": "Transport",
    "amtrak": "Transport", "greyhound": "Transport",
    "parking": "Transport", "toll": "Transport", "dmv": "Transport",
    "gas station": "Transport",

    # ---- ENTERTAINMENT: streaming, movies, gaming, events ----
    "netflix": "Entertainment", "hulu": "Entertainment",
    "disney+": "Entertainment", "disney plus": "Entertainment",
    "hbo max": "Entertainment", "max.com": "Entertainment",
    "spotify": "Entertainment", "apple music": "Entertainment",
    "prime video": "Entertainment", "paramount+": "Entertainment",
    "peacock": "Entertainment", "youtube premium": "Entertainment",
    "amc theatres": "Entertainment", "regal cinemas": "Entertainment",
    "cinemark": "Entertainment", "fandango": "Entertainment",
    "ticketmaster": "Entertainment", "stubhub": "Entertainment",
    "live nation": "Entertainment", "steam games": "Entertainment",
    "playstation network": "Entertainment", "xbox live": "Entertainment",
    "nintendo eshop": "Entertainment", "twitch": "Entertainment",
    "movie": "Entertainment", "cinema": "Entertainment",

    # ---- UTILITIES: internet, phone, power, water, trash ----
    "comcast": "Utilities", "xfinity": "Utilities", "spectrum": "Utilities",
    "at&t": "Utilities", "verizon": "Utilities", "t-mobile": "Utilities",
    "pg&e": "Utilities", "con edison": "Utilities", "national grid": "Utilities",
    "duke energy": "Utilities", "dominion energy": "Utilities",
    "centerpoint energy": "Utilities", "waste management": "Utilities",
    "republic services": "Utilities",
    "electric": "Utilities", "water bill": "Utilities", "gas bill": "Utilities",
    "internet bill": "Utilities", "phone bill": "Utilities",

    # ---- SALARY: payroll / direct deposit ----
    "payroll": "Salary", "paycheck": "Salary", "direct deposit": "Salary",
    "adp payroll": "Salary", "gusto payroll": "Salary",

    # ---- RENT----------------------------------------------
    "apartments": "Rent", "realty": "Rent", "property management": "Rent",
    "leasing office": "Rent", "landlord": "Rent", "mortgage": "Rent",
    "rental": "Rent", "rentals": "Rent",
}


def guess_category(description):
    """Maps purchase description/vendor name to category not always right.
    """
    if not description:
        return "Other"

    desc_lower = description.lower()
    for keyword, category in KEYWORD_RULES.items():
        if keyword in desc_lower:
            return category

    return "Other"


def load_csv(path):
    return pd.read_csv(path)


def normalize_columns(df):
    """Renames headers so that it can easily be placed into database. I tried 
    using some generic possible headers used in your bank statement and ones 
    that appeared in mine. If yours uses a different format feel free to append 
    the details to the lists used."""
    
    df = df.copy()

    # column names to lowercase first,so matching below isn't case-sensitive.
    df.columns = [col.strip().lower() for col in df.columns]

    column_map = {}

    date_candidates = ["date", "transaction date", "posted date"]
    desc_candidates = ["description", "memo", "payee", "details"]
    amount_candidates = ["amount", "transaction amount"]

    for candidate in date_candidates:
        if candidate in df.columns:
            column_map[candidate] = "date"
            break

    for candidate in desc_candidates:
        if candidate in df.columns:
            column_map[candidate] = "description"
            break

    for candidate in amount_candidates:
        if candidate in df.columns:
            column_map[candidate] = "amount"
            break

    df = df.rename(columns=column_map)
    
    if "amount" not in df.columns and "debit" in df.columns and "credit" in df.columns:
        debit = pd.to_numeric(df["debit"], errors="coerce").fillna(0)
        credit = pd.to_numeric(df["credit"], errors="coerce").fillna(0)
        df["amount"] = credit - debit
   

    # Keep only the 3 columns we actually need, in a predictable order.
    df = df[["date", "description", "amount"]]

    #Standardize Date format
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    return df


def compute_row_hash(date, description, amount):
    raw = f"{date}|{description}|{amount}"
    return hashlib.sha256(raw.encode()).hexdigest()


def filter_new_rows(conn, df):
    """Filters out transactions that have already been imported by comparing each transaction's 
    hash with hashes already stored in the database.
    Returns:
    A DataFrame containing only transactions that have not already been imported."""
    
    df = df.copy()
    df["import_hash"] = df.apply(
        lambda row: compute_row_hash(row["date"], row["description"], row["amount"]),
        axis=1
    )


    cursor = conn.cursor()
    cursor.execute("SELECT import_hash FROM transactions WHERE import_hash IS NOT NULL")
    existing_hashes = {row[0] for row in cursor.fetchall()}

    # Keep only rows whose hash is NOT already in the database.
    new_rows = df[~df["import_hash"].isin(existing_hashes)]

    return new_rows

def get_category_id_map(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    return {name: cat_id for cat_id, name in cursor.fetchall()}


def import_csv(conn, path):
    """Imports transactions from a CSV file into the database.

    The CSV is loaded and normalized, duplicate transactions are filtered out,
    new transactions are categorized, and the remaining transactions are inserted into the database.

    Args:
        conn: SQLite database connection.
        path: Path to the CSV file.

    Returns:
        A dictionary containing the number of transactions imported, 
        skipped as duplicates, and assigned to the "Other" category."""
    df = load_csv(path)
    df = normalize_columns(df)
    new_rows = filter_new_rows(conn, df)

    rows_skipped = len(df) - len(new_rows)

    if len(new_rows) == 0:
        return {"rows_imported": 0, "rows_skipped": rows_skipped, "uncategorized_count": 0}

    category_id_map = get_category_id_map(conn)
    uncategorized_count = 0

    # Build a list of tuples ready for a single bulk insert, instead
    # of calling execute() once per row (which is much slower).
    rows_to_insert = []
    for _, row in new_rows.iterrows():
        category = guess_category(row["description"])
        if category == "Other":
            uncategorized_count += 1

        category_id = category_id_map.get(category, category_id_map["Other"])

        rows_to_insert.append((
            row["date"], row["description"], float(row["amount"]),
            category_id, "csv_import", row["import_hash"]
        ))

    # executemany() sends all rows in ONE call instead of looping
    # with execute() per row — significantly faster for bulk inserts.
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO transactions (date, description, amount, category_id, source, import_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows_to_insert)
    conn.commit()

    return {
        "rows_imported": len(rows_to_insert),
        "rows_skipped": rows_skipped,
        "uncategorized_count": uncategorized_count,
    }



if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 csv_importer.py <path_to_csv>")
    else:
        conn = get_connection()
        summary = import_csv(conn, sys.argv[1])
        print(summary)