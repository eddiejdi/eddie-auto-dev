#!/usr/bin/env python3
"""
Busca mensagens no WAHA de produção (homelab)
"""
import requests
import json
import os
from datetime import datetime
import sys
from tools.vault.secret_store import get_field, VaultError

HOMELAB_WAHA = os.environ.get("HOMELAB_WAHA", "http://192.168.15.2:3001")

# Load API key from env or secret store
WAHA_API_KEY = os.environ.get("WAHA_API_KEY")
if not WAHA_API_KEY:
    try:
        WAHA_API_KEY = get_field("eddie/waha_api_key", "password")
    except VaultError:
        WAHA_API_KEY = ""

HEADERS = {
    "X-Api-Key": WAHA_API_KEY,
    "Content-Type": "application/json"
}

def search_waha_production():
    """Busca mensagens no WAHA de produção"""
    print("🔍 Buscando no WAHA de Produção (192.168.15.2:3001)...")
    print("="*80)
    
    try:
        # 1. Verificar health
        print("\n💓 Verificando saúde do serviço...")
        try:
            health = requests.get(f"{HOMELAB_WAHA}/health", headers=HEADERS, timeout=5)
            print(f"  Status: {health.status_code}")
            if health.status_code == 200:
                print(f"  ✓ Resposta: {health.text[:100]}")
        except Exception as e:
            print(f"  ⚠️  Health check falhou: {e}")
        
        # 2. Listar sessões disponíveis
        print("\n📱 Listando sessões WhatsApp...")
        try:
            sessions_resp = requests.get(f"{HOMELAB_WAHA}/api/sessions", headers=HEADERS, timeout=10)
            
            if sessions_resp.status_code == 200:
                sessions = sessions_resp.json()
                print(f"  ✓ Encontradas {len(sessions)} sessões:")
                
                for session in sessions:
                    name = session.get('name', 'unknown')
                    status = session.get('status', 'unknown')
                    print(f"    • {name}: {status}")
                    
                    # Para cada sessão, buscar mensagens recentes
                    print(f"\n    📥 Buscando mensagens da sessão '{name}'...")
                    
                    try:
                        # Tentar diferentes formatos de endpoint
                        endpoints = [
                            f"/api/{name}/messages",
                            f"/api/messages/{name}",
                            f"/api/sessions/{name}/messages"
                        ]
                        
                        messages = None
                        for endpoint in endpoints:
                            try:
                                msg_resp = requests.get(
                                    f"{HOMELAB_WAHA}{endpoint}",
                                    headers=HEADERS,
                                    params={"limit": 50},
                                    timeout=10
                                )
                                
                                if msg_resp.status_code == 200:
                                    messages = msg_resp.json()
                                    print(f"    ✓ Endpoint funcionando: {endpoint}")
                                    break
                            except:
                                continue
                        
                        if messages:
                            print(f"    ✓ Total de mensagens: {len(messages)}")
                            
                            # Filtrar por "nil"
                            nil_messages = []
                            for msg in messages:
                                msg_str = json.dumps(msg).lower()
                                if 'nil' in msg_str:
                                    nil_messages.append(msg)
                            
                            if nil_messages:
                                print(f"\n    🎯 ENCONTRADAS {len(nil_messages)} MENSAGENS COM 'NIL'!")
                                print("    " + "="*76)
                                
                                for msg in nil_messages[:10]:
                                    print(f"\n    📨 ID: {msg.get('id', 'N/A')}")
                                    print(f"    Chat: {msg.get('chatId', msg.get('from', 'N/A'))}")
                                    print(f"    De: {msg.get('participant', msg.get('author', 'N/A'))}")
                                    print(f"    Tipo: {msg.get('type', 'N/A')}")
                                    
                                    body = msg.get('body', '')
                                    if body:
                                        print(f"    Conteúdo: {body[:200]}")
                                    
                                    # Verificar se tem mídia
                                    if msg.get('hasMedia') or msg.get('type') == 'document':
                                        print(f"    📎 TEM MÍDIA/DOCUMENTO!")
                                        print(f"       hasMedia: {msg.get('hasMedia')}")
                                        print(f"       mediaUrl: {msg.get('mediaUrl', 'N/A')}")
                                        
                                        # Se tiver URL de mídia, mostrar
                                        if msg.get('mediaUrl'):
                                            media_url = msg['mediaUrl']
                                            print(f"       URL completa: {HOMELAB_WAHA}{media_url}")
                                    
                                    print(f"    Timestamp: {msg.get('timestamp', 'N/A')}")
                                    print("    " + "-"*76)
                            
                            # Filtrar por PDF/documentos
                            doc_messages = []
                            for msg in messages:
                                msg_str = json.dumps(msg).lower()
                                msg_type = msg.get('type', '')
                                body = msg.get('body', '').lower()
                                
                                if ('pdf' in msg_str or 'document' in msg_type or 
                                    'pdf' in body or 'documento' in body):
                                    doc_messages.append(msg)
                            
                            if doc_messages:
                                print(f"\n    📄 ENCONTRADOS {len(doc_messages)} DOCUMENTOS/PDFs!")
                                print("    " + "="*76)
                                
                                for msg in doc_messages[:5]:
                                    print(f"\n    📎 ID: {msg.get('id', 'N/A')}")
                                    print(f"    Chat: {msg.get('chatId', msg.get('from', 'N/A'))}")
                                    print(f"    Tipo: {msg.get('type', 'N/A')}")
                                    print(f"    Body: {msg.get('body', '')[:100]}")
                                    
                                    if msg.get('mediaUrl'):
                                        print(f"    📥 URL: {HOMELAB_WAHA}{msg['mediaUrl']}")
                                    
                                    print("    " + "-"*76)
                            
                            # Mostrar todas as mensagens recentes
                            print(f"\n    📋 ÚLTIMAS 10 MENSAGENS:")
                            print("    " + "="*76)
                            
                            for msg in messages[:10]:
                                chat_id = msg.get('chatId', msg.get('from', 'N/A'))
                                body = msg.get('body', msg.get('text', ''))
                                ts = msg.get('timestamp', '')
                                msg_type = msg.get('type', 'text')
                                
                                print(f"\n    [{ts}] {chat_id}")
                                print(f"    Tipo: {msg_type}")
                                if body:
                                    print(f"    >>> {body[:150]}")
                                if msg.get('hasMedia'):
                                    print(f"    📎 Com mídia")
                                print("    " + "-"*76)
                        else:
                            print(f"    ⚠️  Nenhum endpoint de mensagens funcionou")
                            print(f"    Tentados: {endpoints}")
                        
                    except Exception as e:
                        print(f"    ❌ Erro ao buscar mensagens: {e}")
            else:
                print(f"  ❌ Erro: Status {sessions_resp.status_code}")
                print(f"  Resposta: {sessions_resp.text[:200]}")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Erro de conexão: {e}")
        
        print("\n" + "="*80)
        print("✓ Busca concluída")
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    search_waha_production()
