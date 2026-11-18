## Group-1 : Assignment 10 (ATM Banking Simulator)

**Course Code:** CS371  
**Year:** 3rd Year, B.Tech  
**Institution:** National Institute of Technology, Meghalaya  

### Team Members
* **B24CS007** - Aishi Pandey
* **B24CS023** - Priya Saha
* **B24CS044** - Rahul Das
* **B24CS046** - Swarnim Suman

# Virtual Bank: ATM Banking Simulator

A small ATM simulator we built in Python for Problem 10. It runs completely offline with Tkinter for the screens and SQLite for storage. All accounts and money are made up, and nothing connects to a real bank.

## What it does

You log in with an account number and PIN, see your balance, and can deposit, withdraw or transfer money. Every transaction is saved with its type, amount and date/time, and you can look back through it on the History page.

We went a bit beyond the minimum requirements, so you can also:

- create a new account from the login screen
- change your PIN
- see a mini statement (your last 5 transactions) on the Overview page
- filter the history by type and export it to a CSV file
- use quick-amount buttons (500, 1000, 2000, 5000) when depositing or withdrawing

A few safety rules are built in too. The account locks after 3 wrong PIN attempts, withdrawals are capped at ₹20,000 per day, and you are logged out automatically after 60 seconds of doing nothing. PINs are never stored as plain text, only as SHA-256 hashes.

## Running it

You need Python 3.8 or newer. There is nothing to install, since `tkinter` and `sqlite3` come with Python. (On some Linux systems you may need `sudo apt install python3-tk`.)

Keep `db.py`, `logic.py` and `gui.py` in the same folder, then run:

```
python gui.py
```

The database file `atm.db` is created automatically the first time you run it. Three sample accounts come ready to use:

| Account no. | PIN  | Starting balance |
|-------------|------|------------------|
| 1001        | 1234 | ₹25,000          |
| 1002        | 4321 | ₹10,000          |
| 1003        | 1111 | ₹5,000           |

If you want to start over, close the app and delete `atm.db`. This also unlocks any account that got locked.

## How the code is organised

We split the project into three files so each one has a single job:

- **`db.py`** opens the database, creates the tables, adds the sample accounts and hashes PINs.
- **`logic.py`** holds all the banking rules (login, deposit, withdraw, transfer, history). It has no Tkinter code in it, so it can be tested without opening a window.
- **`gui.py`** builds every screen and only shows what the logic tells it to.

The database has two tables:

| Table | Columns |
|-------|---------|
| `accounts` | `acc_no` (primary key), `name`, `pin` (hashed), `balance`, `failed_attempts` |
| `transactions` | `id`, `acc_no`, `type`, `amount`, `timestamp`, `balance_after` |

## How the main parts work

**Login.** `login()` looks the account up with a parameterized query and compares the hash of the typed PIN with the stored one. A wrong PIN adds to `failed_attempts`, and at 3 the account is locked.

**Deposits and withdrawals.** The amount is first checked by `parse_amount()`, which uses `try/except ValueError` and rejects anything that isn't a positive number. The balance is then updated with an `UPDATE` query and saved with `commit()`.

**Insufficient funds.** `withdraw()` checks `amount > balance` before touching the database, so a rejected withdrawal changes nothing.

**Transaction history.** After every successful operation, `_record()` inserts a row with the type, amount, the time from `datetime.now()`, and the balance afterwards.

**Errors.** When a rule is broken, the logic raises our own `ATMError`, and the screen catches it and shows the message to the user.

## Limitations

This is a simulation of the transaction logic only. There is no card reader, cash dispenser or network, and everything is stored in one local file. Features like creating an account and transferring money are closer to online banking than to a real ATM, but we included them to make the project more complete.

## Summary

Virtual Bank - ATM Banking Simulator (offline, virtual money)
Run:   python gui.py        (Python 3.8+, no extra installs; uses built-in tkinter + sqlite3)
Sample accounts (acc no / PIN): 1001/1234, 1002/4321, 1003/1111
New accounts can be created from the login screen.
To reset all data: close the app and delete atm.db