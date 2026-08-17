"""SQLite persistence for receipts, bank transactions, and matches."""
import os, sqlite3, json, datetime

DB_PATH = os.environ.get("BILLMATCHER_DB", os.path.expanduser("~/Desktop/bill-matcher/billmatch.db"))


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        merchant TEXT,
        amount REAL,
        date TEXT,
        time TEXT,
        currency TEXT,
        card_last4 TEXT,
        items TEXT,          -- JSON list
        raw_json TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        description TEXT,
        debit REAL,
        credit REAL,
        bank_name TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS matches(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id INTEGER UNIQUE REFERENCES receipts(id),
        txn_id INTEGER REFERENCES transactions(id),
        confidence REAL,
        breakdown TEXT,      -- JSON
        status TEXT,         -- auto | confirmed | rejected | unmatched
        decided_at TEXT
    );
    """)
    c.commit(); c.close()


# ---------- receipts ----------
def add_receipt(r):
    c = _conn()
    cur = c.execute(
        "INSERT INTO receipts(filename,merchant,amount,date,time,currency,card_last4,items,raw_json)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (r.get("filename"), r.get("merchant"), r.get("amount"), r.get("date"),
         r.get("time"), r.get("currency"), r.get("card_last4"),
         json.dumps(r.get("items", []), ensure_ascii=False), json.dumps(r, ensure_ascii=False)))
    c.commit()
    rid = cur.lastrowid; c.close()
    return rid


def all_receipts():
    c = _conn(); rows = c.execute("SELECT * FROM receipts ORDER BY id").fetchall(); c.close()
    return [dict(r) for r in rows]


def get_receipt(rid):
    c = _conn(); r = c.execute("SELECT * FROM receipts WHERE id=?", (rid,)).fetchone(); c.close()
    return dict(r) if r else None


def clear_receipts():
    c = _conn(); c.execute("DELETE FROM receipts"); c.execute("DELETE FROM matches"); c.commit(); c.close()


# ---------- transactions ----------
def add_transactions(txns):
    c = _conn()
    ids = []
    for t in txns:
        cur = c.execute(
            "INSERT INTO transactions(date,description,debit,credit,bank_name) VALUES(?,?,?,?,?)",
            (t.get("date"), t.get("description"), t.get("debit"), t.get("credit"), t.get("bank_name", "")))
        ids.append(cur.lastrowid)
    c.commit(); c.close()
    return ids


def all_transactions():
    c = _conn(); rows = c.execute("SELECT * FROM transactions ORDER BY date").fetchall(); c.close()
    return [dict(r) for r in rows]


def clear_transactions():
    c = _conn(); c.execute("DELETE FROM transactions"); c.commit(); c.close()


# ---------- matches ----------
def upsert_match(receipt_id, txn_id, confidence, breakdown, status):
    c = _conn()
    c.execute("DELETE FROM matches WHERE receipt_id=?", (receipt_id,))
    c.execute(
        "INSERT INTO matches(receipt_id,txn_id,confidence,breakdown,status,decided_at)"
        " VALUES(?,?,?,?,?,datetime('now'))",
        (receipt_id, txn_id, confidence, json.dumps(breakdown, ensure_ascii=False), status))
    c.commit(); c.close()


def set_status(receipt_id, txn_id, status):
    c = _conn()
    if status in ("rejected", "unmatched"):
        c.execute("DELETE FROM matches WHERE receipt_id=?", (receipt_id,))
        c.execute("INSERT INTO matches(receipt_id,txn_id,confidence,breakdown,status,decided_at)"
                  " VALUES(?,?,0,'{}',?,datetime('now'))", (receipt_id, txn_id, status))
    else:
        c.execute("UPDATE matches SET status=?, decided_at=datetime('now') WHERE receipt_id=?", (status, receipt_id))
    c.commit(); c.close()


def all_matches():
    c = _conn()
    rows = c.execute("""
        SELECT m.*, r.merchant r_merchant, r.amount r_amount, r.date r_date,
               t.description t_description, t.date t_date, t.debit t_debit
        FROM matches m
        LEFT JOIN receipts r ON r.id=m.receipt_id
        LEFT JOIN transactions t ON t.id=m.txn_id
        ORDER BY m.confidence DESC
    """).fetchall()
    c.close()
    return [dict(r) for r in rows]


def reset_matches():
    c = _conn(); c.execute("DELETE FROM matches"); c.commit(); c.close()
