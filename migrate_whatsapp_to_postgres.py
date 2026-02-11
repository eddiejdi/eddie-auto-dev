#!/usr/bin/env python3
"""
Script para migrar dados do SQLite para PostgreSQL e inicializar schema
"""
import os
import sys
import sqlite3
import psycopg2
from pathlib import Path

# Configurações
SQLITE_PATH = Path.home() / "eddie-auto-dev" / "whatsapp_data" / "conversations.db"
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://postgres:estou_aqui_dev_2026@localhost:5432/estou_aqui")

def init_postgres_schema():
    """Inicializa schema do WhatsApp no PostgreSQL"""
    print("🔧 Inicializando schema PostgreSQL...")
    
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        
        # Criar schema
        cursor.execute('CREATE SCHEMA IF NOT EXISTS whatsapp')
        print("  ✓ Schema 'whatsapp' criado")
        
        # Criar tabela de mensagens
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whatsapp.messages (
                id SERIAL PRIMARY KEY,
                chat_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_group BOOLEAN DEFAULT FALSE
            )
        ''')
        print("  ✓ Tabela 'messages' criada")
        
        # Criar tabela de sessões
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whatsapp.sessions (
                chat_id TEXT PRIMARY KEY,
                profile TEXT DEFAULT 'assistant',
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  ✓ Tabela 'sessions' criada")
        
        # Criar índices
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_chat 
            ON whatsapp.messages(chat_id, timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
            ON whatsapp.messages(timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_content 
            ON whatsapp.messages USING gin(to_tsvector('portuguese', content))
        ''')
        print("  ✓ Índices criados")
        
        conn.commit()
        conn.close()
        
        print("✅ Schema PostgreSQL inicializado com sucesso!\n")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao inicializar schema: {e}")
        return False

def migrate_from_sqlite():
    """Migra dados do SQLite para PostgreSQL"""
    
    if not SQLITE_PATH.exists():
        print(f"⚠️  Banco SQLite não encontrado: {SQLITE_PATH}")
        print("   (Não há dados para migrar)")
        return True
    
    print(f"📦 Migrando dados do SQLite para PostgreSQL...")
    print(f"   Fonte: {SQLITE_PATH}")
    
    try:
        # Conectar aos dois bancos
        sqlite_conn = sqlite3.connect(SQLITE_PATH)
        pg_conn = psycopg2.connect(POSTGRES_URL)
        
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # Contar registros no SQLite
        sqlite_cursor.execute('SELECT COUNT(*) FROM messages')
        total_messages = sqlite_cursor.fetchone()[0]
        
        if total_messages == 0:
            print("   ℹ️  Nenhuma mensagem para migrar")
            sqlite_conn.close()
            pg_conn.close()
            return True
        
        print(f"   Encontradas {total_messages} mensagens")
        
        # Migrar mensagens
        sqlite_cursor.execute('SELECT chat_id, sender, role, content, timestamp, is_group FROM messages')
        messages = sqlite_cursor.fetchall()
        
        migrated = 0
        for msg in messages:
            try:
                pg_cursor.execute('''
                    INSERT INTO whatsapp.messages (chat_id, sender, role, content, timestamp, is_group)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', msg)
                migrated += 1
            except psycopg2.IntegrityError:
                # Registro já existe, pular
                continue
        
        # Migrar sessões
        sqlite_cursor.execute('SELECT chat_id, profile, last_activity FROM sessions')
        sessions = sqlite_cursor.fetchall()
        
        for sess in sessions:
            try:
                pg_cursor.execute('''
                    INSERT INTO whatsapp.sessions (chat_id, profile, last_activity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chat_id) DO UPDATE 
                    SET profile = EXCLUDED.profile, last_activity = EXCLUDED.last_activity
                ''', sess)
            except Exception as e:
                print(f"   ⚠️  Erro ao migrar sessão: {e}")
        
        pg_conn.commit()
        
        sqlite_conn.close()
        pg_conn.close()
        
        print(f"✅ Migração concluída: {migrated} mensagens, {len(sessions)} sessões\n")
        return True
        
    except Exception as e:
        print(f"❌ Erro na migração: {e}")
        return False

def verify_migration():
    """Verifica se a migração foi bem-sucedida"""
    print("🔍 Verificando migração...")
    
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM whatsapp.messages')
        msg_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM whatsapp.sessions')
        sess_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT chat_id) FROM whatsapp.messages')
        chat_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"  ✓ {msg_count} mensagens")
        print(f"  ✓ {sess_count} sessões")
        print(f"  ✓ {chat_count} chats únicos")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        return False

def main():
    print("="*80)
    print("   MIGRAÇÃO WHATSAPP: SQLite → PostgreSQL")
    print("="*80)
    print()
    
    # 1. Inicializar schema
    if not init_postgres_schema():
        return 1
    
    # 2. Migrar dados (se existirem)
    if not migrate_from_sqlite():
        return 1
    
    # 3. Verificar
    if not verify_migration():
        return 1
    
    print("="*80)
    print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("="*80)
    print()
    print("Próximos passos:")
    print("  1. Reinicie o WhatsApp bot para usar PostgreSQL")
    print("  2. Execute: python3 search_whatsapp_postgres.py")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
