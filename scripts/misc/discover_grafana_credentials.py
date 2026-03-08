#!/usr/bin/env python3
"""
Descobrir e testar credenciais do Grafana local
"""
import subprocess
import os

HOMELAB_HOST = "192.168.15.2"
HOMELAB_USER = "homelab"
SSH_KEY = os.path.expanduser("~/.ssh/id_rsa")

def ssh_cmd(cmd: str) -> str:
    """Executar comando via SSH"""
    try:
        result = subprocess.run(
            ["ssh", "-i", SSH_KEY, f"{HOMELAB_USER}@{HOMELAB_HOST}"],
            input=cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        return f"SSH_ERROR: {e}"

print("🔍 Descobrindo credenciais Grafana local...")
print()

# Tentar encontrar arquivo de configuração local do Grafana
print("1️⃣  Procurando config do Grafana no homelab...")
result = ssh_cmd("find /etc/grafana -name '*.ini' 2>/dev/null | head -1")
print(f"   Config file: {result}")

# Tentar acessar banco de dados do Grafana
print("\n2️⃣  Procurando banco de dados do Grafana...")
result = ssh_cmd("find /var/lib/grafana -name '*.db' 2>/dev/null | head -1")
print(f"   Database: {result}")

# Tentar obter admin API key via dashboard local
print("\n3️⃣  Tentando obter API key via API local...")
result = ssh_cmd("curl -sf -u admin:admin http://localhost:3000/api/auth/keys 2>/dev/null | head -50")
if "error" not in result.lower() and result:
    print(f"   ✅ Acesso com admin:admin funcionou!")
    print(f"   Resultado:{result[:200]}...")
else:
    print(f"   ⚠️  Falha com credenciais padrão")

# Tentar encontrar credenciais em env vars
print("\n4️⃣  Procurando variáveis de ambiente do Grafana...")
result = ssh_cmd("env | grep -i grafana")
if result:
    print(f"   GRAFANA_* env vars: {result}")
else:
    print(f"   Nenhuma variável GRAFANA_* encontrada")

# Tentar obter de arquivo de config
print("\n5️⃣  Procurando senha em arquivos de config...")
result = ssh_cmd("grep -r 'admin' /etc/grafana/*.ini 2>/dev/null | grep -i pass | head -3")
if result:
    print(f"   Encontrado: {result[:100]}...")
else:
    print(f"   Nenhuma senha em config")

print("\n" + "="*60)
print("💡 Se nenhum método funcionou, você pode:")
print("   1. Resetar senha do Grafana no homelab:")
print("      ssh homelab@192.168.15.2")
print("      sudo grafana-cli admin reset-admin-password <nova_senha>")
print("   2. Usar API key criada manualmente via UI do Grafana")
print("   3. Usar Basic Auth (username:password) via curl")
print("="*60)
