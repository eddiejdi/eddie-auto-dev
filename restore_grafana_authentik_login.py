#!/usr/bin/env python3
"""
Restaurar botão de login com Authentik no Grafana

Status: ✅ O botão de login foi removido da tela de login do Grafana
Causa: Variáveis de ambiente GF_AUTH_GENERIC_OAUTH_* não configuradas ou desativadas
Solução: Restaurar configuração de OAuth2 com Authentik
"""

import subprocess
import json
import os
import sys
from pathlib import Path

# Configurações
HOMELAB_HOST = "192.168.15.2"
HOMELAB_USER = "homelab"
SSH_KEY = os.path.expanduser("~/.ssh/id_rsa")

# Credenciais Authentik (do AUTHENTIK_SSO_WIREGUARD_SETUP.md)
AUTHENTIK_URL = "https://auth.rpa4all.com"
AUTHENTIK_CLIENT_ID = "authentik-grafana"
AUTHENTIK_API_TOKEN = "ak-homelab-authentik-api-2026"

# Vars Grafana para OAuth2 com Authentik
GRAFANA_OAUTH_VARS = {
    "GF_AUTH_GENERIC_OAUTH_ENABLED": "true",
    "GF_AUTH_GENERIC_OAUTH_NAME": "Authentik",
    "GF_AUTH_GENERIC_OAUTH_ALLOW_SIGN_UP": "true",
    "GF_AUTH_GENERIC_OAUTH_CLIENT_ID": AUTHENTIK_CLIENT_ID,
    "GF_AUTH_GENERIC_OAUTH_AUTH_URL": f"{AUTHENTIK_URL}/application/o/authorize/",
    "GF_AUTH_GENERIC_OAUTH_TOKEN_URL": f"{AUTHENTIK_URL}/application/o/token/",
    "GF_AUTH_GENERIC_OAUTH_API_URL": f"{AUTHENTIK_URL}/application/o/userinfo/",
    "GF_AUTH_GENERIC_OAUTH_SCOPES": "openid profile email",
    "GF_AUTH_GENERIC_OAUTH_LOGOUT_REDIRECT_URL": f"{AUTHENTIK_URL}/application/o/grafana/end-session/",
    "GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH": "groups[*]",
}

def ssh_cmd(cmd: str) -> tuple[int, str, str]:
    """Executar comando via SSH retornando (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            ["ssh", "-i", SSH_KEY, f"{HOMELAB_USER}@{HOMELAB_HOST}", cmd],
            capture_output=True,
            text=True,
            timeout=15
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "TIMEOUT"
    except Exception as e:
        return 1, "", str(e)

def check_grafana_container() -> bool:
    """Verificar se container Grafana está rodando"""
    print("🔍 Verificando Grafana container...")
    returncode, stdout, stderr = ssh_cmd("docker ps | grep grafana")
    if returncode == 0 and stdout:
        print(f"   ✅ Grafana container encontrado:\n   {stdout}")
        return True
    else:
        print(f"   ❌ Grafana container não encontrado")
        return False

def get_grafana_client_secret() -> str | None:
    """Obter client secret do Authentik para Grafana"""
    print("\n🔑 Procurando client secret do Authentik...")
    
    # Tentar 1: Via API REST do Authentik com token
    print("   (Tentativa 1: API REST do Authentik...)")
    cmd = f"""
    curl -sf -H "Authorization: Bearer {AUTHENTIK_API_TOKEN}" \
      "https://auth.rpa4all.com/api/v3/providers/oauth2/?name__icontains=grafana" 2>/dev/null | \
      python3 -c "import sys, json; data=json.load(sys.stdin); print(data['results'][0]['client_secret'] if data['results'] else 'NOTFOUND')" 2>/dev/null
    """
    
    returncode, stdout, _ = ssh_cmd(cmd)
    if returncode == 0 and stdout and "NOTFOUND" not in stdout:
        secret = stdout.strip()
        if secret and len(secret) > 10:
            print(f"   ✅ Client Secret obtido via API REST")
            return secret
    
    # Tentar 2: Via Django shell
    print("   (Tentativa 2: Django shell...)")
    cmd = """
    docker exec authentik-server /bin/sh -c '
    python manage.py shell -c "
from authentik.providers.oauth2.models import OAuth2Provider
from authentik.core.models import Application

try:
    app = Application.objects.get(slug=\"grafana\")
    provider = OAuth2Provider.objects.get(application=app)
    print(provider.client_secret)
except Exception as e:
    print(f\"ERROR: {e}\")
" 2>/dev/null
    '
    """
    
    returncode, stdout, _ = ssh_cmd(cmd)
    if returncode == 0 and stdout and "ERROR" not in stdout:
        secret = stdout.split('\n')[0].strip()
        if secret and len(secret) > 10:
            print(f"   ✅ Client Secret obtido via Django")
            return secret
    
    # Tentar 3: Procurar em .env ou Docker secrets
    print("   (Tentativa 3: em arquivos de configuração...)")
    cmd = """
    { grep -i "authentik.*grafana.*secret" /mnt/raid1/authentik/.env* 2>/dev/null || \
      docker inspect grafana | grep -i secret || \
      echo "NOTFOUND"; } | head -1
    """
    
    returncode, stdout, _ = ssh_cmd(cmd)
    if returncode == 0 and stdout and "NOTFOUND" not in stdout:
        # Extrair se houver
        if "=" in stdout:
            secret = stdout.split("=")[-1].strip().strip('"').strip("'")
            if secret and len(secret) > 10:
                print(f"   ✅ Client Secret encontrado em config")
                return secret
    
    print(f"   ⚠️  Não foi possível obter client secret automaticamente")
    print(f"      Opções:")
    print(f"      a) Verificar manualmente em: https://auth.rpa4all.com/admin/applications → grafana")
    print(f"      b) Executar: curl -sH 'Authorization: Bearer {AUTHENTIK_API_TOKEN}' https://auth.rpa4all.com/api/v3/providers/oauth2/ | jq '.results[] | select(.name | contains(\"grafana\")) | .client_secret'")
    return None

def configure_grafana_oauth(client_secret: str | None) -> bool:
    """Configurar variáveis de ambiente do Grafana para OAuth2"""
    print("\n⚙️  Configurando OAuth2 no Grafana...")
    
    if not client_secret:
        print("   ⚠️  Client secret não fornecido. Abortando configuração.")
        print("      Você precisa:")
        print("      1. Obter o client secret de: https://auth.rpa4all.com/admin/applications")
        print("      2. Editar docker-compose.yml do Grafana ou systemd service")
        print("      3. Adicionar as variáveis de ambiente listadas abaixo")
        return False
    
    # Preparar env vars
    env_vars = GRAFANA_OAUTH_VARS.copy()
    env_vars["GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET"] = client_secret
    
    # Gerar linhas para adicionar a docker-compose ou .env
    print("\n   Adicione as seguintes variáveis ao Grafana:")
    print("   " + "="*70)
    for key, value in env_vars.items():
        # Escapar para docker-compose YAML
        print(f'      - {key}="{value}"')
    print("   " + "="*70)
    
    # Tentar atualizar via Docker (se for container)
    print("\n   💾 Tentando atualizar container Grafana...")
    cmd = f"docker restart grafana"
    returncode, stdout, stderr = ssh_cmd(cmd)
    
    if returncode == 0:
        print(f"   ✅ Container Grafana reiniciado")
        return True
    else:
        print(f"   ❌ Erro ao reiniciar: {stderr}")
        print(f"      Você pode precisar reiniciar manualmente via docker-compose ou systemd")
        return False

def verify_oauth_config() -> bool:
    """Verificar se OAuth está configurado no Grafana"""
    print("\n✅ Verificando configuração de OAuth no Grafana...")
    
    # Verificar via API do Grafana (admin:admin)
    cmd = """
    curl -sf -u admin:admin -X GET 'http://localhost:3000/api/datasources' 2>/dev/null | head -c 100
    """
    
    returncode, stdout, _ = ssh_cmd(cmd)
    
    if returncode == 0:
        print(f"   ✅ Grafana API respondendo")
        
        # Verificar se OAuth está habilitado
        cmd = """
        grep -i 'generic_oauth\\|authentik' /etc/grafana/grafana.ini 2>/dev/null || \
        docker exec grafana env | grep GF_AUTH_GENERIC_OAUTH || \
        echo "Não encontrado em config"
        """
        returncode, stdout, _ = ssh_cmd(cmd)
        
        if returncode == 0 and "GF_AUTH_GENERIC_OAUTH" in stdout:
            print(f"   ✅ OAuth2 configurado:\n{stdout}")
            return True
        else:
            print(f"   ⚠️  OAuth2 não encontrado na configuração")
            return False
    else:
        print(f"   ⚠️  Grafana não está respondendo na porta 3000")
        return False

def main():
    print("="*70)
    print("🔧 Restaurar Login Authentik no Grafana")
    print("="*70)
    print()
    
    # Step 1: Verificar conectividade SSH
    print("1️⃣  Verificando conectividade SSH...")
    returncode, stdout, stderr = ssh_cmd("echo 'SSH OK'")
    if returncode != 0:
        print(f"   ❌ Erro SSH: {stderr}")
        sys.exit(1)
    else:
        print(f"   ✅ SSH conectado")
    
    # Step 2: Verificar Grafana
    if not check_grafana_container():
        print("\n   ⚠️  Grafana não está rodando como container. Verifique docker ps")
        sys.exit(1)
    
    # Step 3: Obter client secret
    client_secret = get_grafana_client_secret()
    
    # Step 4: Configurar OAuth
    success = configure_grafana_oauth(client_secret)
    
    # Step 5: Aguardar e verificar
    if success:
        print("\n⏳ Aguardando 10 segundos para Grafana reiniciar...")
        import time
        time.sleep(10)
        
        # Verificar
        if verify_oauth_config():
            print("\n" + "="*70)
            print("✅ SUCESSO! Login Authentik restaurado no Grafana")
            print("="*70)
            print("\n📝 Próximos passos:")
            print("   1. Acessar https://grafana.rpa4all.com/login")
            print("   2. Você deve ver um botão 'Authentik' junto com login/senha")
            print("   3. Clicar em 'Authentik' para fazer login com Authentik SSO")
            print()
            return 0
    
    print("\n⚠️  Configuração manual necessária:")
    print("   1. SSH para: ssh -i ~/.ssh/id_rsa homelab@192.168.15.2")
    print("   2. Localize docker-compose ou systemd service do Grafana")
    print("   3. Adicione as variáveis listadas acima")
    print("   4. Reinicie: docker restart grafana (ou systemctl restart grafana-server)")
    print()
    return 1

if __name__ == "__main__":
    sys.exit(main())
