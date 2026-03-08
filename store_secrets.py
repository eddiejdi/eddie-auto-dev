#!/usr/bin/env python3
"""
Script para armazenar credenciais sensíveis no Agent Secrets (Bitwarden/Vaultwarden)

Armazena:
- Credenciais Google Home (Client ID, Client Secret, tokens, Project ID)
- Configuração Gemini 2.5 Pro

Uso:
    python3 store_secrets.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Dados sensíveis para armazenar
SECRETS = {}

def check_bw_cli():
    """Verifica se o Bitwarden CLI está instalado"""
    try:
        result = subprocess.run(["bw", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def store_in_bitwarden(item_name, secrets_dict):
    """Armazena segredos no Bitwarden como Secure Note"""
    try:
        # Criar JSON do item
        item_data = {
            "type": 2,  # Secure Note
            "name": item_name,
            "notes": json.dumps(secrets_dict, indent=2),
            "secureNote": {
                "type": 0
            }
        }
        
        # Codificar como JSON
        item_json = json.dumps(item_data)
        
        # Criar item no Bitwarden
        result = subprocess.run(
            ["bw", "create", "item"],
            input=item_json,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✓ Item '{item_name}' criado no Bitwarden")
            return True
        else:
            print(f"❌ Erro ao criar item: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def store_google_credentials():
    """Armazena credenciais Google Home se existirem"""
    cred_file = Path("google_home_credentials.json")
    
    if not cred_file.exists():
        print("⚠️  Arquivo google_home_credentials.json não encontrado")
        return False
    
    try:
        with open(cred_file) as f:
            creds = json.load(f)
        
        # Armazenar no Bitwarden
        return store_in_bitwarden("shared/google_home_credentials", creds)
        
    except Exception as e:
        print(f"❌ Erro ao processar credenciais Google: {e}")
        return False

def main():
    print("="*60)
    print("ARMAZENAMENTO DE CREDENCIAIS NO AGENT SECRETS")
    print("="*60)
    
    # Verificar se Bitwarden CLI está instalado
    if not check_bw_cli():
        print("\n❌ Bitwarden CLI não instalado!")
        print("\nPara instalar:")
        print("  npm install -g @bitwarden/cli")
        print("\nOu com snap:")
        print("  sudo snap install bw")
        return 1
    
    # Verificar se está logado
    result = subprocess.run(["bw", "status"], capture_output=True, text=True)
    status = json.loads(result.stdout)
    
    if status["status"] != "unlocked":
        print("\n⚠️  Bitwarden vault está travado!")
        print("\nExecute primeiro:")
        print("  bw login")
        print("  export BW_SESSION=$(bw unlock --raw)")
        return 1
    
    print("\n✓ Bitwarden CLI configurado e desbloqueado")
    
    # Armazenar credenciais Google Home (se existirem)
    print("\n📝 Verificando credenciais Google Home...")
    if store_google_credentials():
        print("✓ Credenciais Google Home armazenadas")
    
    # Configurações Gemini 2.5 Pro
    gemini_config = {
        "provider": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash-exp",
        "api_key_env": "GOOGLE_AI_API_KEY",
        "note": "Obtenha API key em https://ai.google.dev/"
    }
    
    print("\n📝 Armazenando configuração Gemini 2.5 Pro...")
    if store_in_bitwarden("shared/gemini_config", gemini_config):
        print("✓ Configuração Gemini armazenada")
    
    print("\n" + "="*60)
    print("✓ CREDENCIAIS ARMAZENADAS COM SUCESSO!")
    print("="*60)
    
    print("\nPara recuperar:")
    print("  bw get item shared/google_home_credentials")
    print("  bw get item shared/gemini_config")
    
    print("\n⚠️  IMPORTANTE: Delete os arquivos locais com credenciais:")
    print("  rm google_home_credentials.json")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada")
        sys.exit(1)
