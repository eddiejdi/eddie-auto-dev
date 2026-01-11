#!/usr/bin/env python3
"""Gmail Expurgo Final - Limpa todas categorias até zerar"""
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def main():
    # Carregar token
    with open('/home/homelab/myClaude/gmail_data/token.json', encoding='utf-8-sig') as f:
        t = json.load(f)
    
    creds = Credentials(
        token=t['token'], 
        refresh_token=t['refresh_token'], 
        token_uri=t['token_uri'], 
        client_id=t['client_id'], 
        client_secret=t['client_secret']
    )
    
    # Refresh se necessário
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        t['token'] = creds.token
        with open('/home/homelab/myClaude/gmail_data/token.json', 'w') as f:
            json.dump(t, f, indent=2)
    
    service = build('gmail', 'v1', credentials=creds)
    
    # Categorias e idade máxima em dias
    categorias = [
        ('promotions', 30),
        ('social', 60),
        ('updates', 90),
        ('forums', 60),
        ('spam', 7)
    ]
    
    total_limpo = 0
    
    for cat, dias in categorias:
        data_limite = (datetime.now() - timedelta(days=dias)).strftime('%Y/%m/%d')
        cat_count = 0
        
        while True:
            try:
                resultado = service.users().messages().list(
                    userId='me', 
                    q=f'category:{cat} before:{data_limite}', 
                    maxResults=100
                ).execute()
                
                msgs = resultado.get('messages', [])
                if not msgs:
                    break
                    
                ids = [m['id'] for m in msgs]
                service.users().messages().batchModify(
                    userId='me', 
                    body={'ids': ids, 'addLabelIds': ['TRASH']}
                ).execute()
                
                cat_count += len(ids)
                total_limpo += len(ids)
                print(f'{cat}: +{len(ids)} movidos (categoria: {cat_count}, total: {total_limpo})')
                
            except Exception as e:
                print(f'Erro em {cat}: {e}')
                break
        
        if cat_count > 0:
            print(f'>>> {cat.upper()}: {cat_count} emails limpos')
        else:
            print(f'>>> {cat.upper()}: Já estava limpo')
    
    print(f'\n=== EXPURGO CONCLUÍDO ===')
    print(f'Total de emails movidos para lixeira: {total_limpo}')
    
    # Verificação final
    print('\n--- Verificação Final ---')
    for cat, dias in categorias:
        data_limite = (datetime.now() - timedelta(days=dias)).strftime('%Y/%m/%d')
        r = service.users().messages().list(
            userId='me', 
            q=f'category:{cat} before:{data_limite}', 
            maxResults=1
        ).execute()
        count = r.get('resultSizeEstimate', 0)
        print(f'{cat} (>{dias}d): {count} restantes')

if __name__ == '__main__':
    main()
