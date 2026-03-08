#!/usr/bin/env python3
"""
Script para buscar mensagens do chat com "nil"
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Diretório de dados do WhatsApp
DATA_DIR = Path(__file__).parent / "whatsapp_data"
DB_PATH = DATA_DIR / "conversations.db"

def search_nil_chat():
    """Busca mensagens do chat com nil"""
    
    if not DB_PATH.exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Buscar todos os chats com "nil" no identificador ou conteúdo
    print("🔍 Buscando mensagens relacionadas a 'nil'...\n")
    
    # 1. Buscar por chat_id contendo "nil"
    cursor.execute('''
        SELECT DISTINCT chat_id, COUNT(*) as msg_count, MAX(timestamp) as last_msg
        FROM messages 
        WHERE lower(chat_id) LIKE '%nil%' OR lower(sender) LIKE '%nil%'
        GROUP BY chat_id
        ORDER BY last_msg DESC
    ''')
    
    chats = cursor.fetchall()
    
    if chats:
        print(f"✓ Encontrados {len(chats)} chats com 'nil':\n")
        for chat_id, msg_count, last_msg in chats:
            print(f"📱 Chat: {chat_id}")
            print(f"   Mensagens: {msg_count}")
            print(f"   Última msg: {last_msg}")
            print()
            
            # Buscar mensagens recentes deste chat
            cursor.execute('''
                SELECT sender, role, content, timestamp
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp DESC
                LIMIT 20
            ''', (chat_id,))
            
            messages = cursor.fetchall()
            
            print(f"   📝 Últimas {len(messages)} mensagens:")
            for sender, role, content, timestamp in messages:
                # Truncar conteúdo longo
                preview = content[:100] + "..." if len(content) > 100 else content
                print(f"   [{timestamp}] {role}: {preview}")
            
            print("\n" + "="*80 + "\n")
    
    # 2. Buscar mensagens que mencionam "pdf", "documento", "arquivo"
    cursor.execute('''
        SELECT chat_id, sender, content, timestamp
        FROM messages
        WHERE (lower(chat_id) LIKE '%nil%' OR lower(sender) LIKE '%nil%')
        AND (
            lower(content) LIKE '%pdf%' OR 
            lower(content) LIKE '%documento%' OR 
            lower(content) LIKE '%arquivo%' OR
            lower(content) LIKE '%anexo%' OR
            lower(content) LIKE '%enviei%'
        )
        ORDER BY timestamp DESC
        LIMIT 10
    ''')
    
    doc_messages = cursor.fetchall()
    
    if doc_messages:
        print("\n📄 Mensagens com possíveis documentos/arquivos:")
        print("="*80)
        for chat_id, sender, content, timestamp in doc_messages:
            print(f"\n[{timestamp}] Chat: {chat_id}")
            print(f"De: {sender}")
            print(f"Conteúdo: {content}")
            print("-"*80)
    
    # 3. Mostrar todas as mensagens do chat nil (últimas 50)
    print("\n\n📋 HISTÓRICO COMPLETO DO CHAT COM NIL:")
    print("="*80)
    
    cursor.execute('''
        SELECT sender, role, content, timestamp
        FROM messages
        WHERE lower(chat_id) LIKE '%nil%' OR lower(sender) LIKE '%nil%'
        ORDER BY timestamp DESC
        LIMIT 50
    ''')
    
    all_messages = cursor.fetchall()
    
    if all_messages:
        print(f"\n✓ Encontradas {len(all_messages)} mensagens:\n")
        for sender, role, content, timestamp in reversed(all_messages):  # Ordem cronológica
            print(f"[{timestamp}] {role.upper()}")
            print(f"De: {sender}")
            print(f">>> {content}")
            print()
    else:
        print("❌ Nenhuma mensagem encontrada com 'nil'")
    
    conn.close()

if __name__ == "__main__":
    search_nil_chat()
