import sqlite3
import bcrypt

# Nova senha para o admin
new_password = "Admin@123"

# Gerar hash bcrypt
password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

print(f"Nova senha: {new_password}")
print(f"Hash gerado: {password_hash}")

# Conectar e atualizar
conn = sqlite3.connect("/app/backend/data/webui.db")
c = conn.cursor()

c.execute("UPDATE auth SET password = ? WHERE email = 'edenilson.teixeira@rpa4all.com'", (password_hash,))
conn.commit()

print(f"Rows affected: {c.rowcount}")

# Verificar
c.execute("SELECT email, password FROM auth WHERE email = 'edenilson.teixeira@rpa4all.com'")
row = c.fetchone()
print(f"Updated: {row[0]} -> {row[1][:30]}...")

conn.close()
print("\nSenha atualizada com sucesso!")
