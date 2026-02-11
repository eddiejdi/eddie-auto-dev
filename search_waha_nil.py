#!/usr/bin/env python3
"""
Busca mensagens do WhatsApp via WAHA API diretamente
"""
import requests
import json
import os
from datetime import datetime
from tools.vault.secret_store import get_field, VaultError

WAHA_URL = os.environ.get("WAHA_URL", "http://localhost:3000")

# Load API key from env or secret store (do NOT hardcode keys in source)
API_KEY = os.environ.get("WAHA_API_KEY")
if not API_KEY:
    try:
        API_KEY = get_field("eddie/waha_api_key", "password")
    except VaultError:
        API_KEY = ""

headers = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json"
}

def search_chats():
    """Busca todos os chats disponíveis"""
    print("🔍 Buscando chats no WAHA...\n")
    
    try:
        # Listar sessões
        resp = requests.get(f"{WAHA_URL}/api/sessions", headers=headers, timeout=5)
        print(f"Status das sessões: {resp.status_code}")
        
        if resp.status_code == 200:
            sessions = resp.json()
            print(f"Sessões: {json.dumps(sessions, indent=2)}\n")
            
            # Para cada sessão, tentar buscar chats
            for session in sessions:
                session_name = session.get('name', 'default')
                print(f"\n📱 Sessão: {session_name}")
                
                # Tentar buscar mensagens
                try:
                    msg_resp = requests.get(
                        f"{WAHA_URL}/api/{session_name}/messages",
                        headers=headers,
                        timeout=5
                    )
                    
                    if msg_resp.status_code == 200:
                        messages = msg_resp.json()
                        print(f"   Mensagens: {len(messages)}")
                        
                        # Filtrar por "nil"
                        nil_messages = [
                            m for m in messages 
                            if 'nil' in str(m).lower()
                        ]
                        
                        if nil_messages:
                            print(f"\n✓ Encontradas {len(nil_messages)} mensagens com 'nil':")
                            for msg in nil_messages[:10]:
                                print(json.dumps(msg, indent=2))
                    else:
                        print(f"   Erro ao buscar mensagens: {msg_resp.status_code}")
                        
                except Exception as e:
                    print(f"   Erro: {e}")
        
        # Tentar endpoint alternativo - listar contatos
        print("\n\n📇 Buscando contatos...")
        try:
            contacts_resp = requests.get(
                f"{WAHA_URL}/api/contacts",
                headers=headers,
                timeout=5
            )
            
            if contacts_resp.status_code == 200:
                contacts = contacts_resp.json()
                print(f"✓ Encontrados {len(contacts)} contatos")
                
                # Filtrar por "nil"
                nil_contacts = [
                    c for c in contacts 
                    if 'nil' in str(c).lower()
                ]
                
                if nil_contacts:
                    print(f"\n✓ Contatos com 'nil': {len(nil_contacts)}")
                    for contact in nil_contacts:
                        print(json.dumps(contact, indent=2))
            else:
                print(f"Erro: {contacts_resp.status_code}")
                
        except Exception as e:
            print(f"Erro ao buscar contatos: {e}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão com WAHA: {e}")
        print("\nTentando endpoints alternativos...")
        
        # Tentar sem autenticação
        try:
            resp = requests.get(f"{WAHA_URL}/", timeout=5)
            print(f"Status root: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
        except Exception as e2:
            print(f"❌ Erro: {e2}")

if __name__ == "__main__":
    search_chats()
