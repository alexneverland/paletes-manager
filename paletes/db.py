import sqlite3
from tkinter import messagebox
from .constants import DB_PATH
import pandas as pd
from .constants import DB_PATH, MAX_DAYS_HISTORY, CARRIERS
import logging
import os

log = logging.getLogger("paletes.db")

def get_connection():
    try:
        conn = sqlite3.connect(
            DB_PATH,
            timeout=30,          # περιμένει αν γράφει άλλος
            check_same_thread=False
        )

        # Multi-user safe settings
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")

        return conn

    except sqlite3.Error as e:
        messagebox.showerror("Σφάλμα Βάσης", f"Σύνδεση απέτυχε: {e}")
        return None


def init_database():
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                carrier TEXT NOT NULL,
                code TEXT,
                name TEXT,
                invoice TEXT,
                left TEXT,
                boxes TEXT,
                comments TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                carrier TEXT NOT NULL,
                name TEXT,
                item_type TEXT,
                count INTEGER,
                comments TEXT
            )
        """)

        conn.commit()

    finally:
        conn.close()

import sqlite3
from datetime import datetime
from .constants import DB_PATH

# =========================
# Entries
# =========================

def insert_entry(entry_date, carrier, code, name, invoice, left, boxes, comments):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entries
        (entry_date, carrier, code, name, invoice, left, boxes, comments)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (entry_date, carrier, code, name, invoice, left, boxes, comments))
    conn.commit()
    conn.close()


def fetch_entries(entry_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, carrier, code, name, invoice, left, boxes, comments
        FROM entries
        WHERE entry_date = ?
        ORDER BY id ASC
    """, (entry_date,))
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_entry(entry_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def update_entry_left(entry_id, left_value):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE entries SET left = ? WHERE id = ?",
        (left_value, entry_id)
    )
    conn.commit()
    conn.close()
import sqlite3
from datetime import datetime, timedelta
from .constants import DB_PATH, MAX_DAYS_HISTORY


def get_db_connection():
    return get_connection()


def clean_old_data():
    cutoff_date = (
        datetime.now() - timedelta(days=MAX_DAYS_HISTORY)
    ).strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM entries WHERE entry_date < ?",
        (cutoff_date,)
    )
    cur.execute(
        "DELETE FROM predictions WHERE entry_date < ?",
        (cutoff_date,)
    )

    deleted_entries = cur.rowcount
    conn.commit()
    conn.close()

    log.info("Cleaned old DB data before %s", cutoff_date)

def fetch_distinct_names_by_carrier():
    conn = get_connection()
    cur = conn.cursor()

    result = {}

    for carrier in CARRIERS:
        names = set()

        cur.execute(
            "SELECT DISTINCT name FROM entries WHERE carrier = ? AND name IS NOT NULL AND name != ''",
            (carrier,)
        )
        for (name,) in cur.fetchall():
            names.add(name)

        cur.execute(
            "SELECT DISTINCT name FROM predictions WHERE carrier = ? AND name IS NOT NULL AND name != ''",
            (carrier,)
        )
        for (name,) in cur.fetchall():
            names.add(name)

        result[carrier] = sorted(names)

    conn.close()
    return result
def fetch_predictions(entry_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, carrier, name, item_type, count, comments
        FROM predictions
        WHERE entry_date = ?
        ORDER BY carrier, name, item_type
    """, (entry_date,))
    rows = cur.fetchall()
    conn.close()
    return rows
def fetch_main_export(entry_date):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT carrier, code, name, invoice, left, boxes, comments
        FROM entries
        WHERE entry_date = ?
        ORDER BY carrier, name, code
        """,
        conn,
        params=(entry_date,)
    )
    conn.close()
    return df

def fetch_entry_by_id(entry_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT code, name, invoice, left, boxes, comments FROM entries WHERE id = ?",
        (entry_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row

def fetch_prediction_export(entry_date):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT carrier, name, item_type, count, comments
        FROM predictions
        WHERE entry_date = ?
        ORDER BY carrier, name, item_type
        """,
        conn,
        params=(entry_date,)
    )
    conn.close()
    return df
def fetch_prediction_by_id(prediction_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT name, item_type, count, comments FROM predictions WHERE id = ?",
        (prediction_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row
def update_entry(entry_id, code, name, invoice, left, boxes, comments):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE entries
        SET code = ?, name = ?, invoice = ?, left = ?, boxes = ?, comments = ?
        WHERE id = ?
        """,
        (code, name, invoice, left, boxes, comments, entry_id)
    )
    conn.commit()
    conn.close()
def insert_prediction(entry_date, carrier, name, item_type, count, comments):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO predictions (entry_date, carrier, name, item_type, count, comments)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (entry_date, carrier, name, item_type, count, comments)
    )
    conn.commit()
    conn.close()


def update_prediction(prediction_id, name, item_type, count, comments):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE predictions
        SET name = ?, item_type = ?, count = ?, comments = ?
        WHERE id = ?
        """,
        (name, item_type, count, comments, prediction_id)
    )
    conn.commit()
    conn.close()
def delete_entries(entry_ids):
    if not entry_ids:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    cur.executemany(
        "DELETE FROM entries WHERE id = ?",
        [(eid,) for eid in entry_ids]
    )

    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted
def delete_predictions(prediction_ids):
    if not prediction_ids:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    cur.executemany(
        "DELETE FROM predictions WHERE id = ?",
        [(pid,) for pid in prediction_ids]
    )

    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted
import shutil
from datetime import date

BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")
MAX_BACKUPS = 14


def auto_backup_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)

    today = date.today().isoformat()
    backup_path = os.path.join(BACKUP_DIR, f"paletes_{today}.db")

    # Αν υπάρχει ήδη backup για σήμερα, δεν ξανακάνουμε
    if os.path.exists(backup_path):
        return

    shutil.copy2(DB_PATH, backup_path)

    # Καθάρισμα παλιών backups
    backups = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("paletes_") and f.endswith(".db")
    )

    if len(backups) > MAX_BACKUPS:
        for old in backups[:-MAX_BACKUPS]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except Exception:
                pass
