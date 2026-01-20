import sqlite3
from tkinter import messagebox
from .constants import DB_PATH

def get_connection():
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as e:
        messagebox.showerror("Σφάλμα Βάσης", f"Σύνδεση απέτυχε: {e}")
        return None

def init_database():
    conn = get_connection()
    if not conn:
        return
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
    except sqlite3.Error as e:
        messagebox.showerror("Σφάλμα Βάσης", f"Αρχικοποίηση πινάκων: {e}")
    finally:
        conn.close()
