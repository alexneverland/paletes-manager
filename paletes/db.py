import sqlite3
import os
import tempfile
import logging
import time
from contextlib import closing
from datetime import datetime, timedelta, date
from tkinter import messagebox
import pandas as pd

from .constants import DB_PATH, MAX_DAYS_HISTORY, CARRIERS

log = logging.getLogger("paletes.db")

# ======================================================
# Connection
# ======================================================

def get_connection():
    conn = None
    try:
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
        conn = sqlite3.connect(
            DB_PATH,
            timeout=30,
            check_same_thread=False
        )
        # Separate office PCs cannot share WAL's shared-memory index.
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA synchronous=FULL;")
        return conn
    except (sqlite3.Error, OSError) as e:
        if conn is not None:
            conn.close()
        messagebox.showerror("Σφάλμα Βάσης", f"Σύνδεση απέτυχε: {e}")
        return None


def get_db_connection():
    return get_connection()

# ======================================================
# Init DB
# ======================================================

def init_database():
    conn = get_connection()
    if conn is None:
        return False

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
        return True

    except sqlite3.Error as e:
        messagebox.showerror("Σφάλμα Βάσης", f"Αρχικοποίηση DB: {e}")
        return False

    finally:
        conn.close()

# ======================================================
# Entries
# ======================================================

def insert_entry(entry_date, carrier, code, name, invoice, left, boxes, comments):
    conn = get_connection()
    if conn is None:
        return
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
    if conn is None:
        return []
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


def fetch_entry_by_id(entry_id):
    conn = get_connection()
    if conn is None:
        return None
    cur = conn.cursor()
    cur.execute("""
        SELECT code, name, invoice, left, boxes, comments
        FROM entries
        WHERE id = ?
    """, (entry_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_entry(entry_id, code, name, invoice, left, boxes, comments):
    conn = get_connection()
    if conn is None:
        return
    cur = conn.cursor()
    cur.execute("""
        UPDATE entries
        SET code = ?, name = ?, invoice = ?, left = ?, boxes = ?, comments = ?
        WHERE id = ?
    """, (code, name, invoice, left, boxes, comments, entry_id))
    conn.commit()
    conn.close()


def update_entry_left(entry_id, left_value):
    conn = get_connection()
    if conn is None:
        return
    cur = conn.cursor()
    cur.execute(
        "UPDATE entries SET left = ? WHERE id = ?",
        (left_value, entry_id)
    )
    conn.commit()
    conn.close()


def delete_entry(entry_id):
    conn = get_connection()
    if conn is None:
        return
    cur = conn.cursor()
    cur.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def delete_entries(entry_ids):
    if not entry_ids:
        return 0
    conn = get_connection()
    if conn is None:
        return 0
    cur = conn.cursor()
    cur.executemany(
        "DELETE FROM entries WHERE id = ?",
        [(eid,) for eid in entry_ids]
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted

# ======================================================
# Predictions
# ======================================================

def insert_prediction(entry_date, carrier, name, item_type, count, comments):
    conn = get_connection()
    if conn is None:
        return
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO predictions
        (entry_date, carrier, name, item_type, count, comments)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entry_date, carrier, name, item_type, count, comments))
    conn.commit()
    conn.close()


def fetch_predictions(entry_date):
    conn = get_connection()
    if conn is None:
        return []
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


def fetch_prediction_by_id(prediction_id):
    conn = get_connection()
    if conn is None:
        return None
    cur = conn.cursor()
    cur.execute("""
        SELECT name, item_type, count, comments
        FROM predictions
        WHERE id = ?
    """, (prediction_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_prediction(prediction_id, name, item_type, count, comments):
    conn = get_connection()
    if conn is None:
        return
    cur = conn.cursor()
    cur.execute("""
        UPDATE predictions
        SET name = ?, item_type = ?, count = ?, comments = ?
        WHERE id = ?
    """, (name, item_type, count, comments, prediction_id))
    conn.commit()
    conn.close()


def delete_predictions(prediction_ids):
    if not prediction_ids:
        return 0
    conn = get_connection()
    if conn is None:
        return 0
    cur = conn.cursor()
    cur.executemany(
        "DELETE FROM predictions WHERE id = ?",
        [(pid,) for pid in prediction_ids]
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted

# ======================================================
# Utils
# ======================================================

def fetch_distinct_names_by_carrier():
    conn = get_connection()
    if conn is None:
        return {}

    cur = conn.cursor()
    result = {}

    for carrier in CARRIERS:
        names = set()

        cur.execute("""
            SELECT DISTINCT name FROM entries
            WHERE carrier = ? AND name IS NOT NULL AND name != ''
        """, (carrier,))
        for (name,) in cur.fetchall():
            names.add(name)

        cur.execute("""
            SELECT DISTINCT name FROM predictions
            WHERE carrier = ? AND name IS NOT NULL AND name != ''
        """, (carrier,))
        for (name,) in cur.fetchall():
            names.add(name)

        result[carrier] = sorted(names)

    conn.close()
    return result


def clean_old_data():
    cutoff_date = (
        datetime.now() - timedelta(days=MAX_DAYS_HISTORY)
    ).strftime("%Y-%m-%d")

    conn = get_connection()
    if conn is None:
        return

    cur = conn.cursor()
    cur.execute("DELETE FROM entries WHERE entry_date < ?", (cutoff_date,))
    cur.execute("DELETE FROM predictions WHERE entry_date < ?", (cutoff_date,))
    conn.commit()
    conn.close()

    log.info("Cleaned old DB data before %s", cutoff_date)

# ======================================================
# Export helpers
# ======================================================

def fetch_main_export(entry_date):
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()

    df = pd.read_sql_query("""
        SELECT carrier, code, name, invoice, left, boxes, comments
        FROM entries
        WHERE entry_date = ?
        ORDER BY carrier, name, code
    """, conn, params=(entry_date,))
    conn.close()
    return df


def fetch_prediction_export(entry_date):
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()

    df = pd.read_sql_query("""
        SELECT carrier, name, item_type, count, comments
        FROM predictions
        WHERE entry_date = ?
        ORDER BY carrier, name, item_type
    """, conn, params=(entry_date,))
    conn.close()
    return df

# ======================================================
# Automatic Backup
# ======================================================

BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")
MAX_BACKUPS = 14


def auto_backup_db():
    today = date.today().isoformat()
    backup_path = os.path.join(BACKUP_DIR, f"paletes_{today}.db")
    temporary_path = None
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        if os.path.exists(backup_path):
            return prune_backups()
        if not os.path.isfile(DB_PATH):
            raise FileNotFoundError(DB_PATH)

        # Each instance writes its own temporary file. Publish only a complete
        # SQLite snapshot, including any committed pages still in an old WAL.
        with tempfile.NamedTemporaryFile(dir=BACKUP_DIR, suffix=".tmp", delete=False) as temp:
            temporary_path = temp.name
        deadline = time.monotonic() + 30

        def check_timeout(status, remaining, total):
            if time.monotonic() > deadline:
                raise TimeoutError("Η βάση παραμένει απασχολημένη για το backup.")

        with closing(sqlite3.connect(DB_PATH, timeout=30)) as source:
            with closing(sqlite3.connect(temporary_path)) as destination:
                source.backup(destination, pages=256, progress=check_timeout, sleep=0.1)
        try:
            # Windows rename fails if another client has already published.
            # POSIX rename replaces the target, so use an exclusive hard link.
            if os.name == 'nt':
                os.rename(temporary_path, backup_path)
                temporary_path = None
            else:
                os.link(temporary_path, backup_path)
        except FileExistsError:
            # Keep the complete snapshot that won the publication race.
            pass
    except (sqlite3.Error, OSError, TimeoutError) as e:
        log.error("Backup failed: %s", e)
        return False
    finally:
        if temporary_path is not None:
            try:
                os.remove(temporary_path)
            except OSError:
                log.exception("Could not remove incomplete backup %s", temporary_path)

    return prune_backups()


def prune_backups():
    try:
        backups = sorted(
            f for f in os.listdir(BACKUP_DIR)
            if f.startswith("paletes_") and f.endswith(".db")
        )
        if len(backups) > MAX_BACKUPS:
            for old in backups[:-MAX_BACKUPS]:
                try:
                    os.remove(os.path.join(BACKUP_DIR, old))
                except FileNotFoundError:
                    # Another client may have pruned the same file.
                    pass
    except OSError as e:
        log.error("Backup retention failed: %s", e)
        return False
    return True
