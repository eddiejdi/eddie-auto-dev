#!/usr/bin/env python3
"""
Script para buscar mensagens no PostgreSQL do WhatsApp
Procura por chat com "nil" e documentos/PDFs
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:estou_aqui_dev_2026@localhost:5432/estou_aqui")

def search_whatsapp_messages():
    """Busca mensagens do WhatsApp no PostgreSQL"""
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✓ Conectado ao PostgreSQL")
        print("="*80)
        
        # 1. Listar todos os chats disponíveis
        print("\n📱 CHATS DISPONÍVEIS:")
        print("-"*80)
        
        cursor.execute('''
            SELECT chat_id, COUNT(*) as msg_count, MAX(timestamp) as last_msg
            FROM whatsapp.messages
            GROUP BY chat_id
            ORDER BY last_msg DESC
        ''')
        
        chats = cursor.fetchall()
        
        if chats:
            for chat in chats:
                print(f"  • {chat['chat_id']}")
                print(f"    Mensagens: {chat['msg_count']} | Última: {chat['last_msg']}")
        else:
            print("  ❌ Nenhum chat encontrado")
        
        # 2. Buscar especificamente por "nil"
        print("\n\n🔍 BUSCANDO CHAT COM 'NIL':")
        print("-"*80)
        
        cursor.execute('''
            SELECT chat_id, sender, role, content, timestamp
            FROM whatsapp.messages
            WHERE lower(chat_id) LIKE %s 
               OR lower(sender) LIKE %s
               OR lower(content) LIKE %s
            ORDER BY timestamp DESC
            LIMIT 20
        ''', ('%nil%', '%nil%', '%nil%'))
        
        nil_messages = cursor.fetchall()
        
        if nil_messages:
            print(f"✓ Encontradas {len(nil_messages)} mensagens relacionadas a 'nil':\n")
            for msg in nil_messages:
                print(f"[{msg['timestamp']}]")
                print(f"Chat: {msg['chat_id']}")
                print(f"De: {msg['sender']} ({msg['role']})")
                print(f">>> {msg['content'][:200]}")
                print()
        else:
            print("❌ Nenhuma mensagem com 'nil' encontrada")
        
        # 3. Buscar mensagens com PDF/documentos
        print("\n\n📄 MENSAGENS COM PDF/DOCUMENTOS:")
        print("-"*80)
        
        cursor.execute('''
            SELECT chat_id, sender, content, timestamp
            FROM whatsapp.messages
            WHERE lower(content) LIKE %s 
               OR lower(content) LIKE %s
               OR lower(content) LIKE %s
               OR lower(content) LIKE %s
            ORDER BY timestamp DESC
            LIMIT 10
        ''', ('%pdf%', '%documento%', '%arquivo%', '%anexo%'))
        
        doc_messages = cursor.fetchall()
        
        if doc_messages:
            print(f"✓ Encontradas {len(doc_messages)} mensagens com documentos:\n")
            for msg in doc_messages:
                print(f"[{msg['timestamp']}] {msg['chat_id']}")
                print(f"De: {msg['sender']}")
                print(f">>> {msg['content']}")
                print()
        else:
            print("❌ Nenhuma mensagem com documentos encontrada")
        
        # 4. Mensagens recentes (últimas 24 horas)
        print("\n\n⏰ MENSAGENS RECENTES (24h):")
        print("-"*80)
        
        yesterday = datetime.now() - timedelta(days=1)
        
        cursor.execute('''
            SELECT chat_id, sender, role, content, timestamp
            FROM whatsapp.messages
            WHERE timestamp > %s
            ORDER BY timestamp DESC
            LIMIT 20
        ''', (yesterday,))
        
        recent = cursor.fetchall()
        
        if recent:
            print(f"✓ {len(recent)} mensagens nas últimas 24 horas:\n")
            for msg in recent:
                print(f"[{msg['timestamp']}] {msg['chat_id']}")
                print(f"{msg['role']}: {msg['content'][:150]}")
                print()
        else:
            print("❌ Nenhuma mensagem recente")
        
        conn.close()
        print("\n" + "="*80)
        print("✓ Busca concluída")
        
        return len(chats) > 0
        
    except psycopg2.Error as e:
        print(f"❌ Erro PostgreSQL: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Buscando mensagens do WhatsApp no PostgreSQL...")
    print()
    
    success = search_whatsapp_messages()
    
    sys.exit(0 if success else 1)
