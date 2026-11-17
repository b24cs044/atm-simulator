"""gui.py - Tkinter interface with a banking-style layout. Run: python gui.py"""
import csv
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

import logic
from db import init_db

# ---------- theme ----------
NAVY, BLUE, LIGHT, WHITE = "#0b2545", "#1a56db", "#f3f6fb", "#ffffff"
GREEN, RED, GREY = "#0e7a3d", "#c62828", "#6b7280"
FONT = ("Segoe UI", 11)
SMALL = ("Segoe UI", 9)
H1 = ("Segoe UI", 20, "bold")
H2 = ("Segoe UI", 13, "bold")
IDLE_MS = 60_000                       # auto-logout after 60 s without activity
IN_TYPES = ("Deposit", "Transfer In")  # shown green; everything else red


def money(x):
    return f"₹{x:,.2f}"


def setup_styles(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure("TButton", font=FONT, padding=7)
    s.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), background=BLUE,
                foreground="white", padding=9)
    s.map("Accent.TButton", background=[("active", "#1747b8")])
    s.configure("TEntry", padding=6)
    s.configure("TCombobox", padding=5)
    s.configure("Treeview", rowheight=28, font=FONT)
    s.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=5)


def make_table(parent, columns, widths, height=None):
    """Treeview with colour tags for money in / money out."""
    tree = ttk.Treeview(parent, columns=columns, show="headings",
                        **({"height": height} if height else {}))
    for c, w in zip(columns, widths):
        tree.heading(c, text=c)
        tree.column(c, anchor="center", width=w)
    tree.tag_configure("in", foreground=GREEN)
    tree.tag_configure("out", foreground=RED)
    return tree


def fill_table(tree, rows):
    """rows: (type, amount, timestamp, balance_after)"""
    tree.delete(*tree.get_children())
    for kind, amount, ts, bal in rows:
        is_in = kind in IN_TYPES
        sign = "+" if is_in else "-"
        tree.insert("", "end", tags=("in" if is_in else "out",),
                    values=(kind, f"{sign}{money(amount)}", ts, money(bal)))


# =====================================================================
#  LOGIN + REGISTER
# =====================================================================
class AuthFrame(tk.Frame):
    """Split screen: navy brand panel on the left, form on the right."""

    def __init__(self, parent, app, heading):
        super().__init__(parent, bg=WHITE)
        self.app = app
        brand = tk.Frame(self, bg=NAVY, width=340)
        brand.pack(side="left", fill="y")
        brand.pack_propagate(False)
        tk.Label(brand, text="HAMARA BANK", font=("Segoe UI", 22, "bold"),
                 bg=NAVY, fg="white").pack(pady=(110, 5))
        tk.Label(brand, text="Secure ATM Simulator", font=FONT, bg=NAVY,
                 fg="#9db7e5").pack()
        tk.Label(brand, text="Hamara Bank • Hamara Paisa", font=SMALL, bg=NAVY,
                 fg="#9db7e5").pack(side="bottom", pady=25)

        self.form = tk.Frame(self, bg=WHITE)
        self.form.pack(side="left", expand=True)
        tk.Label(self.form, text=heading, font=H1, bg=WHITE, fg=NAVY).pack(anchor="w", pady=(0, 15))

    def field(self, label, show=None, width=30):
        tk.Label(self.form, text=label, font=FONT, bg=WHITE, fg=GREY).pack(anchor="w")
        e = ttk.Entry(self.form, font=FONT, width=width, show=show or "")
        e.pack(pady=(2, 10), anchor="w")
        return e


class LoginFrame(AuthFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Sign in")
        self.acc = self.field("Account Number")
        self.pin = self.field("PIN", show="*")           # masked PIN

        self.show_pin = tk.BooleanVar()
        tk.Checkbutton(self.form, text="Show PIN", variable=self.show_pin, bg=WHITE,
                       font=SMALL, command=lambda: self.pin.config(
                           show="" if self.show_pin.get() else "*")).pack(anchor="w")
        self.error = tk.Label(self.form, text="", fg=RED, bg=WHITE, font=SMALL,
                              wraplength=300, justify="left")
        self.error.pack(anchor="w", pady=4)
        ttk.Button(self.form, text="Login", style="Accent.TButton",
                   command=self.do_login).pack(fill="x", pady=(4, 6))
        ttk.Button(self.form, text="Create New Account",
                   command=lambda: app.show("register")).pack(fill="x")
        tk.Label(self.form, text="Sample accounts\n1001 / 1234   1002 / 4321   1003 / 1111",
                 font=SMALL, bg=WHITE, fg=GREY).pack(pady=15)
        self.acc.bind("<Return>", lambda e: self.pin.focus())
        self.pin.bind("<Return>", lambda e: self.do_login())

    def on_show(self):
        for e in (self.acc, self.pin):
            e.delete(0, tk.END)
        self.error.config(text="")
        self.acc.focus()

    def do_login(self):
        try:
            account = logic.login(self.acc.get(), self.pin.get())
        except logic.ATMError as e:
            self.error.config(text=str(e))
            self.pin.delete(0, tk.END)
            return
        self.app.login_success(account)


class RegisterFrame(AuthFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Create account")
        self.name = self.field("Full Name")
        self.acc = self.field("New Account Number (4-12 digits)")
        self.pin = self.field("Set PIN (4 digits)", show="*")
        self.pin2 = self.field("Confirm PIN", show="*")
        self.deposit = self.field("Initial Deposit (₹)")
        self.error = tk.Label(self.form, text="", fg=RED, bg=WHITE, font=SMALL,
                              wraplength=300, justify="left")
        self.error.pack(anchor="w")
        ttk.Button(self.form, text="Register", style="Accent.TButton",
                   command=self.register).pack(fill="x", pady=(6, 6))
        ttk.Button(self.form, text="Back to Login",
                   command=lambda: app.show("login")).pack(fill="x")

    def on_show(self):
        for e in (self.name, self.acc, self.pin, self.pin2, self.deposit):
            e.delete(0, tk.END)
        self.error.config(text="")
        self.name.focus()

    def register(self): # type: ignore
        acc_no = self.acc.get().strip()
        try:
            logic.create_account(acc_no, self.name.get(), self.pin.get(),
                                 self.pin2.get(), self.deposit.get())
        except logic.ATMError as e:
            self.error.config(text=str(e))
            return
        messagebox.showinfo("Success", f"Account {acc_no} created!\nYou can now log in.")
        self.app.show("login")
        self.app.frames["login"].acc.insert(0, acc_no)


# =====================================================================
#  PAGES INSIDE THE BANK WINDOW
# =====================================================================
class Page(tk.Frame):
    def __init__(self, parent, bank, title):
        super().__init__(parent, bg=LIGHT)
        self.bank = bank
        tk.Label(self, text=title, font=H1, bg=LIGHT, fg=NAVY).pack(anchor="w", padx=30, pady=(22, 6))

    @property
    def acc_no(self):
        return self.bank.app.account["acc_no"]

    def card(self, **pack):
        c = tk.Frame(self, bg=WHITE, padx=25, pady=20)
        c.pack(anchor="w", padx=30, pady=8, **pack)
        return c

    def refresh(self):
        pass


class OverviewPage(Page):
    def __init__(self, parent, bank):
        super().__init__(parent, bank, "Account Overview")
        row = tk.Frame(self, bg=LIGHT)
        row.pack(fill="x", padx=30)

        bal = tk.Frame(row, bg=BLUE, padx=25, pady=18)
        bal.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(bal, text="Available Balance", bg=BLUE, fg="#cfe0ff", font=FONT).pack(anchor="w")
        self.balance = tk.Label(bal, bg=BLUE, fg="white", font=("Segoe UI", 28, "bold"))
        self.balance.pack(anchor="w")
        self.acc_lbl = tk.Label(bal, bg=BLUE, fg="#cfe0ff", font=SMALL)
        self.acc_lbl.pack(anchor="w")

        lim = tk.Frame(row, bg=WHITE, padx=25, pady=18)
        lim.pack(side="left", fill="both", expand=True)
        tk.Label(lim, text="Daily Withdrawal Left", bg=WHITE, fg=GREY, font=FONT).pack(anchor="w")
        self.limit = tk.Label(lim, bg=WHITE, fg=NAVY, font=("Segoe UI", 20, "bold"))
        self.limit.pack(anchor="w")
        tk.Label(lim, text=f"Limit: {money(logic.DAILY_LIMIT)} per day", bg=WHITE,
                 fg=GREY, font=SMALL).pack(anchor="w")

        btns = tk.Frame(self, bg=LIGHT)
        btns.pack(anchor="w", padx=30, pady=14)
        for text, page in (("Deposit", "deposit"), ("Withdraw", "withdraw"),
                           ("Transfer", "transfer"), ("Full History", "history")):
            ttk.Button(btns, text=text, width=14,
                       command=lambda p=page: bank.show_page(p)).pack(side="left", padx=(0, 8))

        tk.Label(self, text="Mini Statement (last 5)", font=H2, bg=LIGHT,
                 fg=NAVY).pack(anchor="w", padx=30)
        self.table = make_table(self, ("Type", "Amount", "Date/Time", "Balance After"),
                                (120, 130, 170, 130), height=5)
        self.table.pack(fill="x", padx=30, pady=6)

    def refresh(self):
        self.balance.config(text=money(logic.get_balance(self.acc_no)))
        self.acc_lbl.config(text=f"Account No: {self.acc_no}")
        self.limit.config(text=money(logic.get_daily_remaining(self.acc_no)))
        fill_table(self.table, logic.get_history(self.acc_no, limit=5))


class AmountPage(Page):
    """Shared layout for Deposit and Withdraw."""
    action_text = ""

    def __init__(self, parent, bank, title):
        super().__init__(parent, bank, title)
        self.info = tk.Label(self, bg=LIGHT, fg=GREY, font=FONT, justify="left")
        self.info.pack(anchor="w", padx=30)
        card = self.card()
        tk.Label(card, text="Amount (₹)", font=FONT, bg=WHITE, fg=GREY).pack(anchor="w")
        self.entry = ttk.Entry(card, font=("Segoe UI", 18), width=14)
        self.entry.pack(anchor="w", pady=6)
        quick = tk.Frame(card, bg=WHITE)
        quick.pack(anchor="w", pady=6)
        for amt in (500, 1000, 2000, 5000):
            ttk.Button(quick, text=f"₹{amt:,}", width=8,
                       command=lambda a=amt: self.set_amount(a)).pack(side="left", padx=(0, 6))
        self.msg = tk.Label(card, bg=WHITE, font=FONT, wraplength=420, justify="left")
        self.msg.pack(anchor="w", pady=8)
        ttk.Button(card, text=self.action_text, style="Accent.TButton",
                   command=self.submit).pack(anchor="w")
        self.entry.bind("<Return>", lambda e: self.submit())

    def set_amount(self, amt):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, str(amt))

    def refresh(self):
        self.entry.delete(0, tk.END)
        self.msg.config(text="")
        self.update_info()
        self.entry.focus()

    def submit(self):
        try:
            amount = logic.parse_amount(self.entry.get())
            if not self.confirm(amount):
                return
            new_bal = self.execute(amount) # type: ignore
        except logic.ATMError as e:
            self.msg.config(text=str(e), fg=RED)
            return
        self.entry.delete(0, tk.END)
        self.bank.update_header()
        self.update_info()
        self.msg.config(fg=GREEN, text=self.success_text(amount, new_bal)) # type: ignore

    # overridden by subclasses
    def update_info(self): pass
    def confirm(self, amount): return True


class DepositPage(AmountPage):
    action_text = "Deposit Money"

    def __init__(self, parent, bank):
        super().__init__(parent, bank, "Deposit")

    def update_info(self):
        self.info.config(text=f"Current balance: {money(logic.get_balance(self.acc_no))}")

    def execute(self, amount):
        return logic.deposit(self.acc_no, amount)

    def success_text(self, amount, bal):
        return f"✔ {money(amount)} deposited.  New balance: {money(bal)}"


class WithdrawPage(AmountPage):
    action_text = "Withdraw Money"

    def __init__(self, parent, bank):
        super().__init__(parent, bank, "Withdraw")

    def update_info(self):
        self.info.config(text=f"Current balance: {money(logic.get_balance(self.acc_no))}\n"
                              f"Daily limit left: {money(logic.get_daily_remaining(self.acc_no))}")

    def confirm(self, amount): # type: ignore
        return messagebox.askyesno("Confirm Withdrawal", f"Withdraw {money(amount)}?")

    def execute(self, amount):
        return logic.withdraw(self.acc_no, amount)      # raises ATMError if not allowed

    def success_text(self, amount, bal):
        return f"✔ Please collect your cash: {money(amount)}.  New balance: {money(bal)}"


class TransferPage(Page):
    def __init__(self, parent, bank):
        super().__init__(parent, bank, "Transfer Money")
        self.info = tk.Label(self, bg=LIGHT, fg=GREY, font=FONT)
        self.info.pack(anchor="w", padx=30)
        card = self.card()
        tk.Label(card, text="Recipient Account Number", font=FONT, bg=WHITE, fg=GREY).pack(anchor="w")
        self.to = ttk.Entry(card, font=("Segoe UI", 14), width=20)
        self.to.pack(anchor="w", pady=(2, 12))
        tk.Label(card, text="Amount (₹)", font=FONT, bg=WHITE, fg=GREY).pack(anchor="w")
        self.amount = ttk.Entry(card, font=("Segoe UI", 14), width=20)
        self.amount.pack(anchor="w", pady=(2, 10))
        self.msg = tk.Label(card, bg=WHITE, font=FONT, wraplength=420, justify="left")
        self.msg.pack(anchor="w", pady=6)
        ttk.Button(card, text="Transfer", style="Accent.TButton",
                   command=self.submit).pack(anchor="w")
        self.amount.bind("<Return>", lambda e: self.submit())

    def refresh(self):
        self.to.delete(0, tk.END)
        self.amount.delete(0, tk.END)
        self.msg.config(text="")
        self.info.config(text=f"Current balance: {money(logic.get_balance(self.acc_no))}")
        self.to.focus()

    def submit(self):
        try:
            amount = logic.parse_amount(self.amount.get())
            target = self.to.get().strip()
            if not messagebox.askyesno("Confirm Transfer",
                                       f"Send {money(amount)} to account {target}?"):
                return
            new_bal, name = logic.transfer(self.acc_no, target, amount)
        except logic.ATMError as e:
            self.msg.config(text=str(e), fg=RED)
            return
        self.bank.update_header()
        self.refresh()
        self.msg.config(fg=GREEN, text=f"✔ {money(amount)} sent to {name}.  "
                                       f"New balance: {money(new_bal)}")


class HistoryPage(Page):
    def __init__(self, parent, bank):
        super().__init__(parent, bank, "Transaction History")
        bar = tk.Frame(self, bg=LIGHT)
        bar.pack(fill="x", padx=30, pady=(0, 8))
        tk.Label(bar, text="Filter:", bg=LIGHT, font=FONT).pack(side="left")
        self.filter = ttk.Combobox(bar, state="readonly", width=12,
                                   values=("All", "Deposit", "Withdraw", "Transfer"))
        self.filter.current(0)
        self.filter.pack(side="left", padx=8)
        self.filter.bind("<<ComboboxSelected>>", lambda e: self.load())
        ttk.Button(bar, text="Export to CSV", command=self.export).pack(side="right")

        wrap = tk.Frame(self, bg=LIGHT)
        wrap.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        self.table = make_table(wrap, ("Type", "Amount", "Date/Time", "Balance After"),
                                (120, 130, 170, 130))
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=sb.set)
        self.table.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def refresh(self):
        self.filter.current(0)
        self.load()

    def load(self):
        rows = logic.get_history(self.acc_no)
        choice = self.filter.get()
        if choice != "All":
            rows = [r for r in rows if r[0].startswith(choice)]
        fill_table(self.table, rows)

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="transactions.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Type", "Amount", "Date/Time", "Balance After"])
                w.writerows(logic.get_history(self.acc_no))
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
        except OSError as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")


class PinPage(Page):
    def __init__(self, parent, bank):
        super().__init__(parent, bank, "Change PIN")
        card = self.card()
        self.old = self._field(card, "Current PIN")
        self.new = self._field(card, "New PIN (4 digits)")
        self.new2 = self._field(card, "Confirm New PIN")
        self.msg = tk.Label(card, bg=WHITE, font=FONT, wraplength=380, justify="left")
        self.msg.pack(anchor="w", pady=6)
        ttk.Button(card, text="Update PIN", style="Accent.TButton",
                   command=self.submit).pack(anchor="w")

    @staticmethod
    def _field(card, label):
        tk.Label(card, text=label, font=FONT, bg=WHITE, fg=GREY).pack(anchor="w")
        e = ttk.Entry(card, font=FONT, width=24, show="*")
        e.pack(anchor="w", pady=(2, 10))
        return e

    def refresh(self):
        for e in (self.old, self.new, self.new2):
            e.delete(0, tk.END)
        self.msg.config(text="")

    def submit(self):
        if self.new.get() != self.new2.get():
            self.msg.config(text="New PINs do not match.", fg=RED)
            return
        try:
            logic.change_pin(self.acc_no, self.old.get(), self.new.get())
        except logic.ATMError as e:
            self.msg.config(text=str(e), fg=RED)
            return
        self.refresh()
        self.msg.config(text="✔ PIN changed successfully.", fg=GREEN)


# =====================================================================
#  MAIN BANK WINDOW: header + sidebar + pages
# =====================================================================
class BankFrame(tk.Frame):
    NAV = (("Overview", "overview"), ("Deposit", "deposit"), ("Withdraw", "withdraw"),
           ("Transfer", "transfer"), ("History", "history"), ("Change PIN", "pin"))

    def __init__(self, parent, app):
        super().__init__(parent, bg=LIGHT)
        self.app = app

        header = tk.Frame(self, bg=WHITE, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="HAMARA BANK", font=("Segoe UI", 15, "bold"),
                 bg=WHITE, fg=NAVY).pack(side="left", padx=20)
        self.clock = tk.Label(header, bg=WHITE, fg=GREY, font=SMALL)
        self.clock.pack(side="right", padx=20)
        self.user = tk.Label(header, bg=WHITE, fg=NAVY, font=("Segoe UI", 11, "bold"))
        self.user.pack(side="right", padx=10)
        tk.Frame(self, bg="#dde3ee", height=1).pack(fill="x")

        body = tk.Frame(self, bg=LIGHT)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=NAVY, width=190)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        self.nav_buttons = {}
        for text, page in self.NAV:
            b = tk.Button(side, text=text, anchor="w", font=FONT, bg=NAVY, fg="white",
                          activebackground=BLUE, activeforeground="white", bd=0,
                          padx=22, pady=12, cursor="hand2",
                          command=lambda p=page: self.show_page(p))
            b.pack(fill="x")
            self.nav_buttons[page] = b
        tk.Button(side, text="Logout", anchor="w", font=FONT, bg="#7f1d1d", fg="white",
                  activebackground=RED, activeforeground="white", bd=0, padx=22, pady=12,
                  cursor="hand2", command=app.logout).pack(side="bottom", fill="x")

        content = tk.Frame(body, bg=LIGHT)
        content.pack(side="left", fill="both", expand=True)
        self.pages = {}
        for page, cls in (("overview", OverviewPage), ("deposit", DepositPage),
                          ("withdraw", WithdrawPage), ("transfer", TransferPage),
                          ("history", HistoryPage), ("pin", PinPage)):
            p = cls(content, self)
            p.place(relwidth=1, relheight=1)
            self.pages[page] = p
        self.tick()

    def tick(self):
        self.clock.config(text=datetime.now().strftime("%d %b %Y  %H:%M:%S"))
        self.after(1000, self.tick)

    def update_header(self):
        self.user.config(text=f"{self.app.account['name']}  |  A/C {self.app.account['acc_no']}")

    def show_page(self, name):
        self.update_header()
        self.pages[name].refresh()
        self.pages[name].tkraise()
        for key, b in self.nav_buttons.items():
            b.config(bg=BLUE if key == name else NAVY)

    def on_show(self):
        self.show_page("overview")


# =====================================================================
#  APPLICATION
# =====================================================================
class ATMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hamara Bank - ATM Simulator")
        self.account = None
        self.idle_job = None
        setup_styles(self)
        w, h = 960, 620
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{(self.winfo_screenheight() - h) // 2}")
        self.minsize(900, 600)

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)
        self.frames = {}
        for name, cls in (("login", LoginFrame), ("register", RegisterFrame), ("bank", BankFrame)):
            f = cls(container, self)
            f.place(relwidth=1, relheight=1)
            self.frames[name] = f

        for ev in ("<Any-KeyPress>", "<Any-Button>", "<Motion>"):   # activity resets idle timer
            self.bind_all(ev, self.reset_idle, add="+")
        self.show("login")

    def show(self, name):
        self.frames[name].on_show()
        self.frames[name].tkraise()

    def login_success(self, account):
        self.account = account
        self.show("bank")
        self.reset_idle()

    def logout(self, message=None):
        if self.idle_job:
            self.after_cancel(self.idle_job)
            self.idle_job = None
        self.account = None
        self.show("login")
        if isinstance(message, str):
            messagebox.showinfo("Logged out", message)

    def reset_idle(self, _event=None):
        if self.idle_job:
            self.after_cancel(self.idle_job)
            self.idle_job = None
        if self.account:
            self.idle_job = self.after(IDLE_MS, self.auto_logout)

    def auto_logout(self):
        self.idle_job = None
        self.logout("You were logged out after 60 seconds of inactivity.")


if __name__ == "__main__":
    init_db()
    ATMApp().mainloop()
