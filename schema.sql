CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);


CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT NOT NULL,
    description         TEXT,
    amount              REAL NOT NULL,
    category_id         INTEGER REFERENCES categories(id),
    source              TEXT DEFAULT 'manual',
    import_hash         TEXT,
    recurring_series_id INTEGER REFERENCES recurring_series(id),
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS recurring_series (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_pattern    TEXT NOT NULL,
    category_id         INTEGER REFERENCES categories(id),
    expected_amount     REAL,
    interval_days       INTEGER,
    last_date           TEXT,
    next_expected_date  TEXT,
    active              INTEGER DEFAULT 1
);


CREATE TABLE IF NOT EXISTS budgets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    amount      REAL NOT NULL,
    period      TEXT DEFAULT 'biweekly',
    start_date  TEXT NOT NULL,
    UNIQUE(category_id, start_date)
);

CREATE TABLE IF NOT EXISTS goals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    target_amount  REAL NOT NULL,
    target_date    TEXT,                       
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    active         INTEGER DEFAULT 1
);


CREATE INDEX IF NOT EXISTS idx_transactions_date     ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
