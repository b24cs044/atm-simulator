"""logic.py - all banking rules. No Tkinter code here."""
import math
import sqlite3
from datetime import datetime

from db import get_connection, hash_pin

MAX_ATTEMPTS = 3
DAILY_LIMIT = 20000.0
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class ATMError(Exception):
    """Raised for any rule violation; its message is shown to the user."""


def parse_amount(text: str) -> float:
    """Convert text to a valid positive amount or raise ATMError."""
    try:
        amount = float(text.strip())
    except ValueError:
        raise ATMError("Please enter a valid number.")
    if not math.isfinite(amount) or amount <= 0:
        raise ATMError("Amount must be greater than zero.")
    return round(amount, 2)


def _now() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def _record(conn, acc_no, kind, amount, balance_after):
    conn.execute(
        "INSERT INTO transactions (acc_no, type, amount, timestamp, balance_after) "
        "VALUES (?, ?, ?, ?, ?)", (acc_no, kind, amount, _now(), balance_after))


def login(acc_no: str, pin: str) -> dict:
    """Check account number + PIN. Locks the account after 3 wrong PINs."""
    acc_no, pin = acc_no.strip(), pin.strip()
    if not acc_no or not pin:
        raise ATMError("Enter both account number and PIN.")
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM accounts WHERE acc_no = ?", (acc_no,)).fetchone()
        if row is None:
            raise ATMError("Invalid account number or PIN.")
        if row["failed_attempts"] >= MAX_ATTEMPTS:
            raise ATMError("Account locked after 3 wrong PIN attempts.")
        if row["pin"] != hash_pin(pin):
            attempts = row["failed_attempts"] + 1
            conn.execute("UPDATE accounts SET failed_attempts = ? WHERE acc_no = ?",
                         (attempts, acc_no))
            conn.commit()
            left = MAX_ATTEMPTS - attempts
            if left == 0:
                raise ATMError("Wrong PIN. Account is now locked.")
            raise ATMError(f"Invalid account number or PIN. {left} attempt(s) left.")
        conn.execute("UPDATE accounts SET failed_attempts = 0 WHERE acc_no = ?", (acc_no,))
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def get_balance(acc_no: str) -> float:
    conn = get_connection()
    try:
        return conn.execute("SELECT balance FROM accounts WHERE acc_no = ?",
                            (acc_no,)).fetchone()["balance"]
    finally:
        conn.close()


def deposit(acc_no: str, amount: float) -> float:
    """Add money, log it, return the new balance."""
    if amount <= 0:
        raise ATMError("Amount must be greater than zero.")
    conn = get_connection()
    try:
        conn.execute("UPDATE accounts SET balance = balance + ? WHERE acc_no = ?",
                     (amount, acc_no))
        new_bal = conn.execute("SELECT balance FROM accounts WHERE acc_no = ?",
                               (acc_no,)).fetchone()["balance"]
        _record(conn, acc_no, "Deposit", amount, new_bal)
        conn.commit()
        return new_bal
    except sqlite3.Error:
        conn.rollback()
        raise ATMError("Database error. Transaction cancelled.")
    finally:
        conn.close()


def withdrawn_today(conn, acc_no: str) -> float:
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE acc_no = ? AND type = 'Withdraw' AND timestamp LIKE ?",
        (acc_no, today + "%")).fetchone()
    return row["total"]


def withdraw(acc_no: str, amount: float) -> float:
    """Remove money after the insufficient-funds and daily-limit checks."""
    if amount <= 0:
        raise ATMError("Amount must be greater than zero.")
    conn = get_connection()
    try:
        balance = conn.execute("SELECT balance FROM accounts WHERE acc_no = ?",
                               (acc_no,)).fetchone()["balance"]
        if amount > balance:
            raise ATMError(f"Insufficient funds. Available balance: ₹{balance:,.2f}")
        used = withdrawn_today(conn, acc_no)
        if used + amount > DAILY_LIMIT:
            raise ATMError(f"Daily limit of ₹{DAILY_LIMIT:,.0f} exceeded. "
                           f"You can still withdraw ₹{DAILY_LIMIT - used:,.2f} today.")
        conn.execute("UPDATE accounts SET balance = balance - ? WHERE acc_no = ?",
                     (amount, acc_no))
        new_bal = balance - amount
        _record(conn, acc_no, "Withdraw", amount, new_bal)
        conn.commit()
        return new_bal
    except sqlite3.Error:
        conn.rollback()
        raise ATMError("Database error. Transaction cancelled.")
    finally:
        conn.close()


def change_pin(acc_no: str, old_pin: str, new_pin: str):
    if not (new_pin.isdigit() and len(new_pin) == 4):
        raise ATMError("New PIN must be exactly 4 digits.")
    conn = get_connection()
    try:
        row = conn.execute("SELECT pin FROM accounts WHERE acc_no = ?", (acc_no,)).fetchone()
        if row["pin"] != hash_pin(old_pin):
            raise ATMError("Old PIN is incorrect.")
        conn.execute("UPDATE accounts SET pin = ? WHERE acc_no = ?",
                     (hash_pin(new_pin), acc_no))
        conn.commit()
    finally:
        conn.close()


def get_history(acc_no: str, limit=None) -> list:
    """Newest first. Returns list of (type, amount, timestamp, balance_after)."""
    sql = ("SELECT type, amount, timestamp, balance_after FROM transactions "
           "WHERE acc_no = ? ORDER BY id DESC")
    params = [acc_no]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    conn = get_connection()
    try:
        return [tuple(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ---------- Added features ----------
def get_name(acc_no: str) -> str:
    conn = get_connection()
    try:
        return conn.execute("SELECT name FROM accounts WHERE acc_no = ?",
                            (acc_no,)).fetchone()["name"]
    finally:
        conn.close()


def get_daily_remaining(acc_no: str) -> float:
    """How much can still be withdrawn today."""
    conn = get_connection()
    try:
        return max(0.0, DAILY_LIMIT - withdrawn_today(conn, acc_no))
    finally:
        conn.close()


def create_account(acc_no, name, pin, confirm_pin, initial_text):
    """Register a new account (feature taken from the MySQL version)."""
    acc_no, name = acc_no.strip(), name.strip()
    if not (acc_no.isdigit() and 4 <= len(acc_no) <= 12):
        raise ATMError("Account number must be 4 to 12 digits.")
    if len(name) < 2:
        raise ATMError("Please enter your full name.")
    if not (pin.isdigit() and len(pin) == 4):
        raise ATMError("PIN must be exactly 4 digits.")
    if pin != confirm_pin:
        raise ATMError("PINs do not match.")
    try:
        initial = float(initial_text.strip() or "0")
    except ValueError:
        raise ATMError("Initial deposit must be a number.")
    if not math.isfinite(initial) or initial < 0:
        raise ATMError("Initial deposit cannot be negative.")
    initial = round(initial, 2)

    conn = get_connection()
    try:
        conn.execute("INSERT INTO accounts (acc_no, name, pin, balance) VALUES (?, ?, ?, ?)",
                     (acc_no, name, hash_pin(pin), initial))
        if initial > 0:
            _record(conn, acc_no, "Deposit", initial, initial)
        conn.commit()
    except sqlite3.IntegrityError:          # PRIMARY KEY already exists
        conn.rollback()
        raise ATMError("This account number already exists.")
    except sqlite3.Error:
        conn.rollback()
        raise ATMError("Database error. Account was not created.")
    finally:
        conn.close()


def transfer(from_acc: str, to_acc: str, amount: float):
    """Move money between two accounts. Returns (new_balance, recipient_name)."""
    to_acc = to_acc.strip()
    if not to_acc:
        raise ATMError("Enter the recipient account number.")
    if to_acc == from_acc:
        raise ATMError("You cannot transfer to your own account.")
    if amount <= 0:
        raise ATMError("Amount must be greater than zero.")
    conn = get_connection()
    try:
        recipient = conn.execute("SELECT name FROM accounts WHERE acc_no = ?",
                                 (to_acc,)).fetchone()
        if recipient is None:
            raise ATMError("Recipient account not found.")
        balance = conn.execute("SELECT balance FROM accounts WHERE acc_no = ?",
                               (from_acc,)).fetchone()["balance"]
        if amount > balance:
            raise ATMError(f"Insufficient funds. Available balance: ₹{balance:,.2f}")
        conn.execute("UPDATE accounts SET balance = balance - ? WHERE acc_no = ?", (amount, from_acc))
        conn.execute("UPDATE accounts SET balance = balance + ? WHERE acc_no = ?", (amount, to_acc))
        new_bal = balance - amount
        _record(conn, from_acc, "Transfer Out", amount, new_bal)
        rbal = conn.execute("SELECT balance FROM accounts WHERE acc_no = ?",
                            (to_acc,)).fetchone()["balance"]
        _record(conn, to_acc, "Transfer In", amount, rbal)
        conn.commit()          # both updates succeed together or not at all
        return new_bal, recipient["name"]
    except sqlite3.Error:
        conn.rollback()
        raise ATMError("Database error. Transfer cancelled.")
    finally:
        conn.close()
