import requests
import os
import json

waha_host = os.getenv('WAHA_HOST', '192.168.15.2')
waha_port = os.getenv('WAHA_PORT', '3001')
waha_url = f'http://{waha_host}:{waha_port}'

# Get chats
r = requests.get(f'{waha_url}/api/default/chats', timeout=10)
data = r.json()

print('='*70)
print('📱 GRUPOS WHATSAPP E MENSAGENS RECENTES')
print('='*70)

# Handle both list and dict responses
if isinstance(data, dict):
    chats = data.get('chats', [])
elif isinstance(data, list):
    chats = data
else:
    print(f"Tipo inesperado: {type(data)}")
    print(json.dumps(data, indent=2)[:500])
    chats = []

for chat in chats[:10]:
    print(f"\n🔹 {chat.get('name', 'Sem nome')}")
    print(f"   ID: {chat.get('id', 'N/A')}")
    
    # Get recent messages from this chat
    chat_id = chat.get('id')
    if chat_id:
        try:
            msgs_r = requests.get(f'{waha_url}/api/default/chats/{chat_id}/messages?limit=5', timeout=10)
            if msgs_r.status_code == 200:
                messages = msgs_r.json()
                for i, msg in enumerate(messages[:5], 1):
                    body = msg.get('body', '')
                    if body and len(body) > 20:
                        print(f"   [{i}] {body[:300]}")
        except Exception as e:
            print(f"   ⚠️ Erro ao buscar mensagens: {e}")
            
print(f"\n✅ Total de {len(chats)} chats encontrados")
