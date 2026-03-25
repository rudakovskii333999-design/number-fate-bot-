import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'donations.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS donations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  amount REAL,
                  date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS manual_donations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  amount REAL,
                  date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def add_donation(amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO donations (amount) VALUES (?)", (amount,))
    conn.commit()
    conn.close()

def add_manual_donation(amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO manual_donations (amount) VALUES (?)", (amount,))
    conn.commit()
    conn.close()

def get_total_donations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount), 0) FROM donations")
    total = c.fetchone()[0]
    conn.close()
    return total

def get_total_manual_donations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount), 0) FROM manual_donations")
    total = c.fetchone()[0]
    conn.close()
    return total

def reset_donations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM donations")
    c.execute("DELETE FROM manual_donations")
    conn.commit()
    conn.close()