#!/usr/bin/env python3
"""Verificar banco de dados do interceptor"""
import sqlite3
from pathlib import Path

db_path = Path('/home/eddie/myClaude/specialized_agents/agent_rag/interceptor.db')
print(f'DB existe: {db_path.exists()}')

if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Verificar tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f'Tabelas: {tables}')
    
    # Contar registros
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {table[0]}')
        count = cursor.fetchone()[0]
        print(f'  {table[0]}: {count} registros')
    
    # Ver conversas
    cursor.execute('SELECT * FROM conversations ORDER BY started_at DESC LIMIT 5')
    convs = cursor.fetchall()
    print(f'\nConversas: {len(convs)}')
    for c in convs:
        print(f'  {c}')
    
    # Ver últimas mensagens
    cursor.execute('SELECT * FROM messages ORDER BY timestamp DESC LIMIT 5')
    msgs = cursor.fetchall()
    print(f'\nÚltimas mensagens: {len(msgs)}')
    for m in msgs:
        print(f'  {m}')
    
    conn.close()
else:
    print("Banco de dados não existe!")
