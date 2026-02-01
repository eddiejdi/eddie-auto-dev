#!/usr/bin/env python3
"""
Script para configurar Open WebUI:
1. Habilitar API Keys
2. Adicionar senha local para usuário OAuth
"""

import sqlite3
import secrets
import os
import sys

# Possíveis locais do banco de dados
DB_PATHS = [
    "/home/homelab/open-webui/data/webui.db",
    "/home/homelab/.open-webui/webui.db",
    "/var/lib/open-webui/webui.db",
    "/app/backend/data/webui.db",
    os.path.expanduser("~/.open-webui/webui.db"),
]


def find_db():
    """Encontra o banco de dados do Open WebUI"""
    for path in DB_PATHS:
        if os.path.exists(path):
            return path

    # Procurar em volumes Docker
    import subprocess

    try:
        result = subprocess.run(
            ["find", "/home", "-name", "webui.db", "-type", "f"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except:
        pass

    return None


def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha (formato Open WebUI)"""
    try:
        import bcrypt

        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()
    except ImportError:
        # Fallback para passlib
        try:
            from passlib.hash import bcrypt as passlib_bcrypt

            return passlib_bcrypt.hash(password)
        except ImportError:
            print("ERRO: Instale bcrypt: pip install bcrypt")
            sys.exit(1)


def main():
    print("=" * 60)
    print("  Open WebUI - Configurador de Senha Local")
    print("=" * 60)
    print()

    # Encontrar banco de dados
    db_path = find_db()
    if not db_path:
        print("ERRO: Banco de dados nao encontrado!")
        print("Locais verificados:")
        for p in DB_PATHS:
            print(f"  - {p}")
        sys.exit(1)

    print(f"Banco de dados: {db_path}")

    # Conectar
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Listar tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tabelas: {', '.join(tables)}")

    # Verificar estrutura da tabela user
    if "user" in tables:
        cursor.execute("PRAGMA table_info(user)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Colunas user: {', '.join(columns)}")

        # Listar usuarios
        cursor.execute("SELECT id, email, name, role FROM user")
        users = cursor.fetchall()
        print(f"\nUsuarios ({len(users)}):")
        for u in users:
            print(f"  - {u['email']} ({u['role']})")

    # Verificar tabela auth
    if "auth" in tables:
        cursor.execute("PRAGMA table_info(auth)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"\nColunas auth: {', '.join(columns)}")

        cursor.execute("SELECT * FROM auth")
        auths = cursor.fetchall()
        print(f"Registros auth: {len(auths)}")
        for a in auths:
            print(f"  - {dict(a)}")

    # Perguntar qual usuario configurar
    print("\n" + "-" * 60)
    email = input("Email do usuario para definir senha (ou Enter para sair): ").strip()

    if not email:
        print("Saindo...")
        conn.close()
        return

    # Verificar se usuario existe
    cursor.execute("SELECT id, email, name FROM user WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user:
        print(f"Usuario nao encontrado: {email}")
        conn.close()
        return

    print(f"Usuario encontrado: {user['name']} ({user['email']})")

    # Definir nova senha
    new_password = input("Nova senha (ou Enter para gerar automatica): ").strip()
    if not new_password:
        new_password = secrets.token_urlsafe(12)
        print(f"Senha gerada: {new_password}")

    # Hash da senha
    password_hash = hash_password(new_password)

    # Verificar se existe registro em auth
    cursor.execute("SELECT * FROM auth WHERE id = ?", (user["id"],))
    auth_record = cursor.fetchone()

    if auth_record:
        # Atualizar
        cursor.execute(
            "UPDATE auth SET password = ? WHERE id = ?", (password_hash, user["id"])
        )
        print("Senha atualizada!")
    else:
        # Inserir
        cursor.execute(
            "INSERT INTO auth (id, email, password, active) VALUES (?, ?, ?, ?)",
            (user["id"], email, password_hash, True),
        )
        print("Registro de autenticacao criado!")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("  CONFIGURACAO CONCLUIDA!")
    print("=" * 60)
    print(f"\n  Email: {email}")
    print(f"  Senha: {new_password}")
    print("\n  Agora voce pode fazer login via email/senha!")
    print("=" * 60)


if __name__ == "__main__":
    main()
