#!/usr/bin/env python3
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

CREDENTIALS_FILE = '/home/eddie/myClaude/credentials.json'
TOKEN_FILE = '/home/eddie/myClaude/gmail_data/token.json'

def main():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        print('Token existente carregado')
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print('Renovando token...')
            creds.refresh(Request())
        else:
            print('Iniciando autorizacao OAuth...')
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, prompt='consent', open_browser=False)
            print('Autorizacao concluida!')
        
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print(f'Token salvo em: {TOKEN_FILE}')
    
    print('Autenticacao Gmail pronta!')
    return creds

if __name__ == '__main__':
    main()
