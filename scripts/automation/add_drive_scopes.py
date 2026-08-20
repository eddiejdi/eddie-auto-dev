#!/usr/bin/env python3
"""
Adiciona escopos do Drive ao token existente do Gmail
Requer reautenticação via OAuth
"""
import json
import sys
from pathlib import Path

# Diretórios
GMAIL_TOKEN = Path('/home/homelab/myClaude/gmail_data/token.json')
DRIVE_DIR = Path('/home/homelab/myClaude/drive_data')
DRIVE_TOKEN = DRIVE_DIR / 'token.json'
DRIVE_CREDS = DRIVE_DIR / 'credentials.json'

# Novos escopos
DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

def main():
    print("="*80)
    print("🔐 ADICIONAR ESCOPOS DO DRIVE")
    print("="*80)
    
    # Verificar se token Gmail existe
    if not GMAIL_TOKEN.exists():
        print(f"\n❌ Token do Gmail não encontrado: {GMAIL_TOKEN}")
        sys.exit(1)
    
    # Carregar token Gmail
    with open(GMAIL_TOKEN) as f:
        token_data = json.load(f)
    
    print("\n✓ Token Gmail carregado")
    print(f"  Escopos atuais: {len(token_data.get('scopes', []))}")
    
    # Adicionar escopos do Drive
    current_scopes = token_data.get('scopes', [])
    new_scopes = list(set(current_scopes + DRIVE_SCOPES))
    
    print("\n📂 Adicionando escopos do Drive...")
    print(f"  Novos escopos totais: {len(new_scopes)}")
    
    # Criar novo token
    new_token = token_data.copy()
    new_token['scopes'] = new_scopes
    
    # Criar diretório drive_data
    DRIVE_DIR.mkdir(exist_ok=True)
    
    # Salvar novo token
    with open(DRIVE_TOKEN, 'w') as f:
        json.dump(new_token, f, indent=2)
    
    print(f"\n✅ Token salvo: {DRIVE_TOKEN}")
    
    # Copiar credenciais se não existirem
    if not DRIVE_CREDS.exists():
        creds_source = Path('/home/homelab/myClaude/credentials.json')
        if creds_source.exists():
            import shutil
            shutil.copy(creds_source, DRIVE_CREDS)
            print(f"✅ Credenciais copiadas: {DRIVE_CREDS}")
    
    print("\n" + "="*80)
    print("⚠️  IMPORTANTE:")
    print("="*80)
    print("""
Este token pode NÃO funcionar se o Google exigir reautenticação
para adicionar novos escopos.

Se o script falhar com erro de permissão, será necessário:

1. Executar: python3 setup_google_apis.py
2. Autorizar novamente no navegador
3. Os novos escopos serão adicionados

Mas vamos tentar usar o token atualizado primeiro...
""")
    
    return True

if __name__ == "__main__":
    main()
