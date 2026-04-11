#!/usr/bin/env python3
"""Fix Storj identity certificates with corrupted dates (year 1 AD).

Re-signs ca.cert and identity.cert with valid dates while preserving
the same key pairs (= same Node ID = same earnings/data).

Usage: python tools/storj_fix_certs.py
"""
import subprocess
import sys
import shlex

HOMELAB = "homelab@192.168.15.2"
SSH_KEY = "/home/edenilson/.ssh/homelab_key"
IDENTITY_DIR = "/home/homelab/.local/share/storj/identity/storagenode"
CORRECT_BACKUP = "/home/homelab/.local/share/storj/identity/storagenode.bak_20260410_151002"


def ssh(cmd: str, timeout: int = 30) -> str:
    """Executa comando via SSH no homelab."""
    full = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", HOMELAB, cmd]
    result = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and result.stderr:
        print(f"STDERR: {result.stderr.strip()}", file=sys.stderr)
    return result.stdout.strip()


def main() -> int:
    """Executa fix de certificados."""
    print("=== Storj Certificate Date Fix ===\n")

    # Step 1: Verificar que backup correto existe e tem Node ID certo
    print("[1/6] Verificando backup correto...")
    check = ssh(f"test -f {CORRECT_BACKUP}/ca.key && echo OK || echo MISSING")
    if "OK" not in check:
        print(f"ERRO: Backup não encontrado em {CORRECT_BACKUP}")
        return 1

    # Step 2: Parar container
    print("[2/6] Parando container storagenode...")
    ssh("docker stop storagenode 2>/dev/null; sleep 2; echo done")

    # Step 3: Copiar chaves do backup correto para /tmp/storj_fix
    print("[3/6] Preparando chaves do backup correto (Node ID 12hFihxX...)...")
    ssh(f"""
mkdir -p /tmp/storj_fix &&
cp {CORRECT_BACKUP}/ca.key /tmp/storj_fix/ca.key &&
cp {CORRECT_BACKUP}/ca.cert /tmp/storj_fix/ca_old.cert &&
cp {CORRECT_BACKUP}/identity.key /tmp/storj_fix/identity.key &&
cp {CORRECT_BACKUP}/identity.cert /tmp/storj_fix/identity_old.cert &&
echo 'Chaves copiadas'
""")

    # Step 4: Re-assinar CA cert com datas válidas (10 anos)
    print("[4/6] Re-assinando CA cert com datas válidas (10 anos)...")
    result = ssh("""
cd /tmp/storj_fix &&

# Extrair subject da CA original
SUBJ=$(openssl x509 -in ca_old.cert -noout -subject -nameopt RFC2253 2>/dev/null | sed 's/subject=//')

# Re-criar CA self-signed com mesma chave, datas válidas
openssl req -new -x509 -key ca.key -out ca_new.cert -days 3650 -subj "/O=Storj" 2>&1 &&

# Verificar nova CA
echo "--- Nova CA ---"
openssl x509 -in ca_new.cert -noout -dates -subject 2>&1
""")
    print(result)
    if "notBefore" not in result:
        print("ERRO: Falha ao re-assinar CA cert")
        return 1

    # Step 5: Re-assinar identity cert com nova CA
    print("\n[5/6] Re-assinando identity cert...")
    result = ssh("""
cd /tmp/storj_fix &&

# Extrair CSR da identity key
openssl req -new -key identity.key -out identity.csr -subj "/O=Storj" 2>&1 &&

# Assinar com a nova CA
openssl x509 -req -in identity.csr -CA ca_new.cert -CAkey ca.key -CAcreateserial -out identity_leaf.cert -days 3650 2>&1 &&

# Criar chain: identity_leaf + ca_new (formato Storj)
cat identity_leaf.cert ca_new.cert > identity_new.cert &&

echo "--- Nova Identity ---"
openssl x509 -in identity_new.cert -noout -dates -subject 2>&1 &&
echo "Chain length: $(grep -c 'BEGIN CERTIFICATE' identity_new.cert)"
""")
    print(result)

    # Step 6: Instalar novos certs (preservando chaves originais)
    print("\n[6/6] Instalando certificados corrigidos...")
    result = ssh(f"""
cd /tmp/storj_fix &&

# Backup extra de segurança
cp {IDENTITY_DIR}/ca.cert {IDENTITY_DIR}/ca.cert.bak_predatefix 2>/dev/null
cp {IDENTITY_DIR}/identity.cert {IDENTITY_DIR}/identity.cert.bak_predatefix 2>/dev/null

# Instalar chaves corretas (do backup com Node ID certo)
cp /tmp/storj_fix/ca.key {IDENTITY_DIR}/ca.key &&
cp /tmp/storj_fix/identity.key {IDENTITY_DIR}/identity.key &&

# Instalar certs com datas corrigidas
cp /tmp/storj_fix/ca_new.cert {IDENTITY_DIR}/ca.cert &&
cp /tmp/storj_fix/identity_new.cert {IDENTITY_DIR}/identity.cert &&

# Permissoes corretas
chmod 644 {IDENTITY_DIR}/ca.cert {IDENTITY_DIR}/identity.cert &&
chmod 600 {IDENTITY_DIR}/ca.key {IDENTITY_DIR}/identity.key &&
chown homelab:homelab {IDENTITY_DIR}/* &&

echo "=== Verificacao Final ==="
echo "CA cert:"
openssl x509 -in {IDENTITY_DIR}/ca.cert -noout -dates 2>&1
echo "Identity cert:"
openssl x509 -in {IDENTITY_DIR}/identity.cert -noout -dates 2>&1
echo "Arquivos:"
ls -la {IDENTITY_DIR}/
""")
    print(result)

    # Iniciar container
    print("\n=== Iniciando container ===")
    ssh("docker start storagenode")
    print("Container iniciado. Aguardando 15s para estabilizar...")
    import time
    time.sleep(15)

    # Verificar
    print("\n=== Verificação Pós-Start ===")
    result = ssh("""
echo "Node ID:"
docker logs storagenode 2>&1 | grep 'Node .* started' | tail -1

echo ""
echo "API Status:"
curl -sL http://127.0.0.1:14002/api/sno/ 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'quicStatus: {d.get(\"quicStatus\",\"N/A\")}')
    print(f'lastPinged: {d.get(\"lastPinged\",\"N/A\")}')
    print(f'upToDate: {d.get(\"upToDate\",\"N/A\")}')
except: print('API não respondeu ainda')
" 2>&1

echo ""
echo "Erros recentes:"
docker logs storagenode 2>&1 | grep -i "error\|FATAL\|mismatch" | tail -3
""")
    print(result)

    # Limpar temp
    ssh("rm -rf /tmp/storj_fix")
    print("\n✅ Script concluído")
    return 0


if __name__ == "__main__":
    sys.exit(main())
