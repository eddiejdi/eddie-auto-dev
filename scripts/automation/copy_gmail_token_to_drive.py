#!/usr/bin/env python3
"""
Copiar credenciais de Gmail para Drive
O Gmail já foi autorizado anteriormente
"""
import json
import pickle
from pathlib import Path
import shutil

GMAIL_TOKEN = Path('/home/homelab/myClaude/gmail_data/token.json')
DRIVE_DIR = Path('/home/homelab/myClaude/drive_data')
DRIVE_TOKEN = DRIVE_DIR / 'token.json'

DRIVE_DIR.mkdir(exist_ok=True)

if GMAIL_TOKEN.exists():
    print("✅ Copiando token do Gmail para Drive...")
    shutil.copy(GMAIL_TOKEN, DRIVE_TOKEN)
    
    # Ler e adicionar escopos do Drive
    with open(DRIVE_TOKEN) as f:
        token = json.load(f)
    
    # Adicionar escopos se não existem
    if 'drive.readonly' not in str(token.get('scopes', [])):
        token['scopes'] = list(set(token.get('scopes', []) + [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/drive.metadata.readonly'
        ]))
        
        with open(DRIVE_TOKEN, 'w') as f:
            json.dump(token, f, indent=2)
        
        print("✅ Escopos do Drive adicionados")
    
    print(f"✅ Token copiado para: {DRIVE_TOKEN}")
    print(f"   Escopos: {len(token.get('scopes', []))}")
else:
    print(f"❌ Token do Gmail não encontrado: {GMAIL_TOKEN}")
