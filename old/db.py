import sqlite3

def init_db():
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY, datetime TEXT, text TEXT)''')
    conn.commit()
    conn.close()

def add_event(datetime_str, text):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('INSERT INTO events (datetime, text) VALUES (?, ?)', (datetime_str, text))
    conn.commit()
    conn.close()

def get_events():
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('SELECT * FROM events')
    events = c.fetchall()
    conn.close()
    return events
