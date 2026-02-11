#!/usr/bin/env python3
import requests, json
from datetime import datetime

WAHA = "http://192.168.15.2:3001"
KEY = "757fae2686eb44479b9a34f1b62dbaf3"
H = {"X-Api-Key": KEY}

chats = requests.get(f"{WAHA}/api/default/chats", headers=H).json()
print(f"Total chats: {len(chats)}\n")

for chat in chats[:15]:
    cid = chat['id']
    msgs = requests.get(f"{WAHA}/api/default/chats/{cid}/messages?limit=20", headers=H).json()
    print(f"\n{'='*80}\nChat: {cid} ({len(msgs)} msgs)")
    
    for msg in msgs[:10]:
        ts = datetime.fromtimestamp(msg['timestamp']).strftime('%Y-%m-%d %H:%M')
        body = (msg.get('body') or '')[:150]
        has_media = msg.get('hasMedia', False)
        
        # Buscar "nil"
        if 'nil' in str(msg).lower():
            print(f"  🎯 [{ts}] NIL ENCONTRADO: {body}")
        
        # Buscar PDF
        if has_media or 'pdf' in body.lower() or msg.get('type') == 'document':
            print(f"  📎 [{ts}] DOC: {body} (media:{has_media})")
        
        print(f"  [{ts}] {body}")
