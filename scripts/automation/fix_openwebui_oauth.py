#!/usr/bin/env python3
"""
Restaurar login Authentik no Open WebUI

Análogo ao script para Grafana, mas com configuração específica do Open WebUI.
"""

import subprocess
import os
import sys
import time

HOMELAB_HOST = "192.168.15.2"
HOMELAB_USER = "homelab"
SSH_KEY = os.path.expanduser("~/.ssh/id_rsa")

AUTHENTIK_URL = "https://auth.rpa4all.com"
AUTHENTIK_API_TOKEN = "ak-homelab-authentik-api-2026"

def ssh_cmd(cmd: str) -> tuple[int, str, str]:
    """Executar via SSH"""
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

def fix_openwebui():
    """Restaurar OAuth2 no Open WebUI"""
    print("="*70)
    print("🔧 Restaurar Login Authentik no Open WebUI")
    print("="*70)
    print()
    
    # Step 1: Verificar SSH
    print("1️⃣  Verificando SSH...")
    rc, out, err = ssh_cmd("echo OK")
    if rc != 0:
        print(f"   ❌ Erro: {err}")
        return False
    print("   ✅ SSH OK")
    
    # Step 2: Verificar container
    print("\n2️⃣  Verificando Open WebUI container...")
    rc, out, err = ssh_cmd("docker ps | grep open-webui")
    if rc != 0 or not out:
        print(f"   ❌ Container não encontrado")
        return False
    print(f"   ✅ Container rodando")
    
    # Step 3: Obter client secret
    print("\n3️⃣  Obtendo client secret do Authentik...")
    cmd = f"""
    curl -sf -H "Authorization: Bearer {AUTHENTIK_API_TOKEN}" \
      "https://auth.rpa4all.com/api/v3/providers/oauth2/?name__icontains=openwebui" 2>/dev/null | \
      python3 -c "import sys, json; data=json.load(sys.stdin); print(data['results'][0]['client_secret'] if data['results'] else 'NOTFOUND')" 2>/dev/null
    """
    rc, secret, _ = ssh_cmd(cmd)
    if rc != 0 or not secret or "NOTFOUND" in secret:
        print(f"   ⚠️  Não conseguiu obter secret")
        return False
    print(f"   ✅ Secret obtido")
    
    # Step 4: Restaurar variáveis
    print("\n4️⃣  Restaurando variáveis de ambiente...")
    
    env_vars = {
        "OPENID_PROVIDER_URL": f"https://auth.rpa4all.com/application/o/openwebui/.well-known/openid-configuration",
        "OAUTH_CLIENT_ID": "authentik-openwebui",
        "OAUTH_CLIENT_SECRET": secret,
        "OAUTH_PROVIDER_NAME": "Authentik",
        "OAUTH_SCOPES": "openid profile email",
        "ENABLE_OAUTH_SIGN_UP": "True",
    }
    
    # Atualizar via docker
    for key, value in env_vars.items():
        quoted_value = value.replace("'", "'\\''")
        cmd = f"""docker exec open-webui bash -c "echo 'export {key}=\"{quoted_value}\"' >> ~/.bashrc" 2>/dev/null || true"""
        ssh_cmd(cmd)
    
    # Step 5: Restart
    print("\n5️⃣  Reiniciando Open WebUI...")
    rc, _, err = ssh_cmd("docker restart open-webui")
    if rc == 0:
        print("   ✅ Container reiniciado")
        time.sleep(5)
    else:
        print(f"   ⚠️  Erro ao reiniciar: {err}")
    
    # Step 6: Verificar
    print("\n6️⃣  Verificando...")
    time.sleep(3)
    rc, out, _ = ssh_cmd("docker logs open-webui 2>&1 | tail -20 | grep -i 'oauth\\|authentik\\|listening'")
    if "listening" in out.lower():
        print("   ✅ Open WebUI restaurado!")
        return True
    else:
        print("   ⚠️  Verificar logs: docker logs open-webui")
        return False

if __name__ == "__main__":
    success = fix_openwebui()
    print("\n" + "="*70)
    if success:
        print("✅ SUCESSO! Acesse https://openwebui.rpa4all.com/")
        print()
        print("Se ainda estiver travado:")
        print("  - Limpar cache do navegador (Ctrl+Shift+Del)")
        print("  - Verificar logs: ssh homelab@192.168.15.2 'docker logs open-webui'")
    else:
        print("⚠️  Verificar manualmente via SSH:")
        print("  ssh homelab@192.168.15.2")
        print("  docker logs open-webui")
    print("="*70)
    sys.exit(0 if success else 1)
