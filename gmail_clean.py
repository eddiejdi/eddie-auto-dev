#!/usr/bin/env python3
"""Gmail Cleaner - Versão Ultra Simples"""
import os, json, base64
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN = "/home/homelab/myClaude/gmail_data/token.json"
DB = "/home/homelab/myClaude/gmail_data/emails_db.json"
LOG = "/home/homelab/myClaude/gmail_data/cleaner.log"

PROMO = ['cupom','desconto','oferta','promoção','sale','off','compre','newsletter',
         'marketing','unsubscribe','vip','win','giveaway','prize','mkt@','kucoin',
         'shopee','aliexpress','insider','loja','store','@email.']

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, 'a') as f: f.write(line + '\n')

def main():
    log("=" * 50)
    log("🚀 INICIANDO LIMPEZA DE EMAILS")
    
    # Carregar credenciais
    with open(TOKEN, encoding='utf-8-sig') as f:
        t = json.load(f)
    
    creds = Credentials(token=t['token'], refresh_token=t.get('refresh_token'),
                       token_uri=t['token_uri'], client_id=t['client_id'],
                       client_secret=t['client_secret'])
    
    if creds.expired and creds.refresh_token:
        log("🔄 Renovando token...")
        creds.refresh(Request())
        t['token'] = creds.token
        with open(TOKEN, 'w') as f: json.dump(t, f, indent=2)
    
    svc = build('gmail', 'v1', credentials=creds)
    
    # Buscar emails
    log("📥 Buscando emails...")
    res = svc.users().messages().list(userId='me', maxResults=30, labelIds=['INBOX']).execute()
    msgs = res.get('messages', [])
    log(f"📧 Encontrados: {len(msgs)} emails")
    
    # Carregar DB
    db = {'emails': [], 'ids': []}
    if os.path.exists(DB):
        with open(DB) as f: db = json.load(f)
    
    stats = {'total': len(msgs), 'trained': 0, 'removed': 0}
    
    for i, m in enumerate(msgs):
        try:
            log(f"[{i+1}/{len(msgs)}] Processando...")
            data = svc.users().messages().get(userId='me', id=m['id'], format='full').execute()
            hdrs = {h['name']: h['value'] for h in data['payload']['headers']}
            
            subj = hdrs.get('Subject', 'Sem assunto')
            sender = hdrs.get('From', 'Desconhecido')
            snippet = data.get('snippet', '')
            
            # Classificar
            text = (subj + ' ' + sender + ' ' + snippet).lower()
            is_promo = any(p in text for p in PROMO)
            
            if is_promo:
                log(f"🗑️ REMOVENDO: {subj[:40]}")
                svc.users().messages().trash(userId='me', id=m['id']).execute()
                stats['removed'] += 1
            else:
                if m['id'] not in db['ids']:
                    db['emails'].append({
                        'id': m['id'], 'subject': subj, 'sender': sender,
                        'snippet': snippet, 'date': hdrs.get('Date', ''),
                        'indexed': datetime.now().isoformat()
                    })
                    db['ids'].append(m['id'])
                    stats['trained'] += 1
                    log(f"🧠 TREINADO: {subj[:40]}")
                    
        except Exception as e:
            log(f"❌ Erro: {e}")
    
    # Salvar
    with open(DB, 'w') as f: json.dump(db, f, indent=2, ensure_ascii=False)
    
    log("=" * 50)
    log(f"📊 RESULTADO: {stats['total']} total, {stats['trained']} treinados, {stats['removed']} removidos")
    log(f"💾 Base: {len(db['emails'])} emails")
    log("=" * 50)
    
    # Salvar stats
    with open("/home/homelab/myClaude/gmail_data/last_run.json", 'w') as f:
        json.dump({**stats, 'timestamp': datetime.now().isoformat()}, f)

if __name__ == '__main__':
    main()
