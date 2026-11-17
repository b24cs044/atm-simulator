"""db.py - database connection, table creation and sample data."""
import hashlib
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atm.db")


def hash_pin(pin: str) -> str:
    """PINs are stored as SHA-256 hashes, never as plain text."""
    return hashlib.sha256(pin.encode()).hexdigest()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # access columns by name
    return conn


def init_db():
    """Create tables (if missing) and seed sample accounts (if empty)."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                acc_no          TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                pin             TEXT NOT NULL,
                balance         REAL NOT NULL DEFAULT 0,
                failed_attempts INTEGER NOT NULL DEFAULT 0
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                acc_no        TEXT NOT NULL,
                type          TEXT NOT NULL,
                amount        REAL NOT NULL,
                timestamp     TEXT NOT NULL,
                balance_after REAL NOT NULL,
                FOREIGN KEY (acc_no) REFERENCES accounts(acc_no)
            )""")
        if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
            samples = [
                ("1001", "Aarav Sharma", hash_pin("1234"), 25000.0),
                ("1002", "Kavya Singh", hash_pin("4321"), 10000.0),
                ("1003", "Rohan Das", hash_pin("1111"), 5000.0),
            ]
            conn.executemany(
                "INSERT INTO accounts (acc_no, name, pin, balance) VALUES (?, ?, ?, ?)",
                samples)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database ready at", DB_PATH)
