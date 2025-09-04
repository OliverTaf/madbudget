import os, sqlite3, json
from contextlib import closing

DB_PATH = "data/madbudget.db"
os.makedirs("data", exist_ok=True)

def get_conn():
    return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)

def init_db():
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,           -- 'YYYY-MM-DD'
            text TEXT DEFAULT '',
            category TEXT DEFAULT '',
            type TEXT NOT NULL CHECK(type IN ('spend','topup')),
            amount REAL NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )""")

def load_transactions_df():
    import pandas as pd
    with closing(get_conn()) as conn:
        df = pd.read_sql_query(
            "SELECT id,date,text,category,type,amount FROM transactions ORDER BY date DESC,id DESC",
            conn
        )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df

def insert_transaction(date_str, text, category, type_, amount):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO transactions(date,text,category,type,amount) VALUES (?,?,?,?,?)",
            (date_str, text, category, type_, float(amount))
        )

def save_setting(key, value):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, default=str))
        )

def load_setting(key, default=None):
    with closing(get_conn()) as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
    return (json.loads(row[0]) if row else default)

