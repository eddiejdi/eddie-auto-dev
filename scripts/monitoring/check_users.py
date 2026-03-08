import sqlite3
conn = sqlite3.connect("/app/backend/data/webui.db")
c = conn.cursor()

print("=== USERS ===")
c.execute("SELECT id, email, name, role FROM user")
for row in c.fetchall():
    print(row)

print("\n=== AUTH TABLE ===")
c.execute("SELECT id, email FROM auth")
for row in c.fetchall():
    print(row)

print("\n=== TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in c.fetchall()])
