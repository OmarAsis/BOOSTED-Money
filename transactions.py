from datetime import datetime
from db_control import get_connection

def get_amount():
    """Gets abs value of transaction from user input
    Returns:
        amount:float
    """
    while True:
        try:
            amount=float(input("What is the transaction amount? "))
            break
        except ValueError:
            print("Transaction Amount should be a floating absolute value with no commas/periods for seperation.\n")
            print("For example 10,000 would be written as 10000")
            continue
    return amount
            
def get_nature():
    """Gets nature of transaction aka (+/-) in the form of Deposit/Expense
    Returns:
        str: "-" or None
    """
    while True:
        nature_of_transaction=input("Is this an Expense or a Deposit: ")
        if nature_of_transaction.lower() not in ("expense", "deposit"):
            print("Make sure you type expense/deposit properly there should be no attached punctuation")
        else:
            break
    if nature_of_transaction.lower()=="expense":
        return "-"
    else:
        return None
        
def categorize():
    """Outputs list of categories that transactions are divided into to help later data_analysis
        User selects from list where it is returned

    Returns:
        trans_category: str
    """
    CATEGORIES = ["Food", "Rent", "Utilities", "Transport", "Entertainment", "Salary", "Other"]
    while True:
        for number,CATEGORY in enumerate(CATEGORIES,1):
            print(f"{number}. {CATEGORY}")      
        trans_category=input(f"Pick a Category from the above:  ")
        if trans_category not in CATEGORIES:
            print(f"Category chosen must be in the below. Restart!\n________________")
            continue
        break
    return trans_category

def get_date():
    """ Collects date of transaction from user in form of (MM/DD/YYYY)

    Returns:
        date: str
    """
    while True:
        date_input = input("Enter date (MM/DD/YYYY): ")
        try:
            date = datetime.strptime(date_input, "%m/%d/%Y").date()
            break
        except ValueError:
            print("Invalid date. Try again.")
    date=date.strftime("%Y-%m-%d")
    return date

def get_description():
    """Gets optional description of transaction if user opts in

    Returns:
        transaction_description: str
    """
    while True:
        choice=input("Would you live to add a description(Y/N)")
        if choice!="Y" and choice!="N" :
            print("Pick Y or N")
            continue
        if choice=="Y":
            transaction_description=input("Description: ")
        else:
            transaction_description=None
        break
    return transaction_description

# Dont want to call the database all the time.
# With cache it will populated with info from categories.
#Eventually wont need to check database
_category_id_cache = {}


def get_category_id(conn, name):
    """_summary_

    Args:
        conn (conn): conn to categories table in database
        name (str): category name given by categorize()

    Returns:
        category_id: category id of corresponding category
    """
    if name in _category_id_cache:
        return _category_id_cache[name]

    cursor = conn.cursor()
    cursor.execute("SELECT id FROM categories WHERE name = ?", (name,))
    row = cursor.fetchone()# row is a tuple so must index row[0] to get id
    _category_id_cache[name] = row[0]
    return row[0]
 
def insert_transaction(conn, date, description, amount, category_id):
    """Inserts transaction into transaction table of database given all info needed
    like(date, description, amount, category_id).
    Returns id of added row
    """
    
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (date, description, amount, category_id, source)
        VALUES (?, ?, ?, ?, ?)
    """, (date, description, amount, category_id, "manual"))
    conn.commit()
    return cursor.lastrowid
 
def add_Transaction():
    """ Gets nature of transaction,amount,date,category, then inserts transaction into table
    and returns id of added row
    Returns:
        txn_id: id of added row
    """
    nature_of_transaction = get_nature()
    transaction_amount = get_amount()
    transaction_category = categorize()
    description = get_description()
    date = get_date()
    if nature_of_transaction == "-":
        transaction_amount = -transaction_amount
    conn = get_connection()
    category_id = get_category_id(conn, transaction_category)
    txn_id = insert_transaction(conn, date, description, transaction_amount, category_id)
    return txn_id




def get_transaction(conn, txn_id):
    #Fetches a single transaction by id
    cursor = conn.cursor()
    cursor.execute("""
        SELECT transactions.id, transactions.date, transactions.description,
               transactions.amount, categories.name
        FROM transactions
        JOIN categories ON transactions.category_id = categories.id
        WHERE transactions.id = ?
    """, (txn_id,))
    return cursor.fetchone()

def edit_transaction(conn, txn_id, date=None, description=None, amount=None, category=None):
    """_summary_

    Args:
        conn (conn): connection to transaction database.
        txn_id (num): id of transaction to be edited
        date (str, optional):Defaults to None.
        description (str, optional): Defaults to None.
        amount (float, optional): Defaults to None.
        category (str, optional): Defaults to None.

    Returns:
        row_count: total rows edited
    """
    existing = get_transaction(conn, txn_id)
    if existing is None:
        print(f"No transaction found with id {txn_id}.")
        return False

    cursor = conn.cursor()
    # Build the SET clause dynamically, same pattern as search
    fields_to_update = []
    values = []

    if date is not None:
        fields_to_update.append("date = ?")
        values.append(date)

    if description is not None:
        fields_to_update.append("description = ?")
        values.append(description)

    if amount is not None:
        fields_to_update.append("amount = ?")
        values.append(amount)

    if category is not None:
        category_id = get_category_id(conn, category)
        fields_to_update.append("category_id = ?")
        values.append(category_id)

    if not fields_to_update:
        print("No fields provided to update.")
        return False

    # Join all the "column = ?" pieces with commas:
    set_clause = ", ".join(fields_to_update)

    values.append(txn_id)

    query = f"UPDATE transactions SET {set_clause} WHERE id = ?"
    cursor.execute(query, tuple(values))
    conn.commit()

    return cursor.rowcount > 0  # rowcount = how many rows were changed


def remove_transaction(conn, txn_id):
    existing = get_transaction(conn, txn_id)
    if existing is None:
        print(f"No transaction found with id {txn_id}.")
        return False

    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    conn.commit()

    return cursor.rowcount > 0


if __name__ == "__main__":
    new_id = add_Transaction()
    print(f"Saved! New transaction id: {new_id}")
