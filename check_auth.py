import sqlite3

conn = sqlite3.connect("/app/backend/data/webui.db")
c = conn.cursor()

print("=== AUTH TABLE STRUCTURE ===")
c.execute("PRAGMA table_info(auth)")
for row in c.fetchall():
    print(row)

print("\n=== AUTH DATA (full) ===")
c.execute("SELECT * FROM auth WHERE email='edenilson.adm@gmail.com'")
row = c.fetchone()
if row:
    print(f"Columns: {len(row)}")
    print(f"Data: {row}")
