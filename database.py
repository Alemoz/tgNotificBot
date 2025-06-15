import sqlite3

conn = sqlite3.connect("events.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    days TEXT,
    date TEXT,
    time TEXT,
    description TEXT
)
''')
conn.commit()

def add_event(event_type, days, date, time, description):
    cursor.execute("INSERT INTO events (type, days, date, time, description) VALUES (?, ?, ?, ?, ?)",
                   (event_type, days, date, time, description))
    conn.commit()

def get_all_events():
    cursor.execute("SELECT * FROM events")
    return cursor.fetchall()

def delete_event(event_id):
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
