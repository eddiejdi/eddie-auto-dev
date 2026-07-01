#!/bin/bash
# Backup Authentik + Vaultwarden (self-hosted) + Bitwarden (cloud) → vault LUKS pendrive
# Pré-requisito: sudo ./vault-open.sh open
set -euo pipefail

MOUNT_POINT="/mnt/vault"
HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"
HOMELAB_SSH_KEY="${HOMELAB_SSH_KEY:-/home/edenilson/.ssh/homelab_key}"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_ROOT="$MOUNT_POINT/backups"
LOG="$BACKUP_ROOT/backup.log"
STORJ_KEYS_ROOT="$MOUNT_POINT/keys/storj"
STORJ_WALLET_DIR="$STORJ_KEYS_ROOT/wallet"
STORJ_IDENTITY_DIR="$STORJ_KEYS_ROOT/identity"

# Paths reais confirmados no homelab
AUTHENTIK_MEDIA_PATH="/mnt/raid1/authentik/media"
VAULTWARDEN_DATA_PATH="/home/homelab/myClaude/tools/vaultwarden/data"
STORJ_API_URL="${STORJ_API_URL:-http://127.0.0.1:14002/api/sno/}"
STORJ_PAYOUT_URL="${STORJ_PAYOUT_URL:-http://127.0.0.1:14002/api/sno/estimated-payout}"
STORJ_CONFIG_PATH="${STORJ_CONFIG_PATH:-/mnt/storj8tb/storj/data/config.yaml}"
STORJ_IDENTITY_PATH="${STORJ_IDENTITY_PATH:-/home/homelab/.local/share/storj/identity/storagenode}"
STORJ_WALLET_KEYSTORE_FILE="${STORJ_WALLET_KEYSTORE_FILE:-}"
STORJ_WALLET_PRIVATE_KEY_FILE="${STORJ_WALLET_PRIVATE_KEY_FILE:-}"
STORJ_WALLET_MNEMONIC_FILE="${STORJ_WALLET_MNEMONIC_FILE:-}"
STORJ_WALLET_KEYSTORE_REMOTE_FILE="${STORJ_WALLET_KEYSTORE_REMOTE_FILE:-}"
STORJ_WALLET_PRIVATE_KEY_REMOTE_FILE="${STORJ_WALLET_PRIVATE_KEY_REMOTE_FILE:-}"
STORJ_WALLET_MNEMONIC_REMOTE_FILE="${STORJ_WALLET_MNEMONIC_REMOTE_FILE:-}"

# ── helpers ──────────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
die()  { echo "ERRO: $*" >&2; exit 1; }
ssh_run() { ssh -o ConnectTimeout=10 -o BatchMode=yes -i "$HOMELAB_SSH_KEY" "$HOMELAB_USER@$HOMELAB_HOST" "$@"; }
rsync_run() { rsync -e "ssh -o ConnectTimeout=10 -o BatchMode=yes -i $HOMELAB_SSH_KEY" "$@"; }

trim_old_backups() {
    local pattern="$1"
    local keep="$2"
    find "$(dirname "$pattern")" -name "$(basename "$pattern")" -printf '%T@ %p\n' \
        | sort -rn | tail -n "+$((keep + 1))" | awk '{print $2}' | xargs -r rm
}

copy_optional_secret() {
    local label="$1"
    local local_src="$2"
    local remote_src="$3"
    local dest="$4"

    if [ -n "$local_src" ]; then
        if [ -f "$local_src" ]; then
            install -m 600 "$local_src" "$dest"
            log "[Storj] ${label}: copiado de origem local"
            return 0
        fi
        log "[Storj] AVISO: ${label} local configurado mas não encontrado: $local_src"
        return 1
    fi

    if [ -n "$remote_src" ]; then
        if ssh_run "test -f '$remote_src'"; then
            ssh_run "cat '$remote_src'" > "$dest"
            chmod 600 "$dest"
            log "[Storj] ${label}: copiado do homelab"
            return 0
        fi
        log "[Storj] AVISO: ${label} remoto configurado mas não encontrado: $remote_src"
    fi

    return 1
}

write_storj_manifest() {
    local status_file="$1"
    local payout_file="$2"
    local manifest_file="$3"

    python3 - "$status_file" "$payout_file" "$manifest_file" "$STORJ_WALLET_DIR" "$STORJ_IDENTITY_DIR" "$HOMELAB_HOST" "$STORJ_API_URL" "$STORJ_PAYOUT_URL" "$STORJ_CONFIG_PATH" "$STORJ_IDENTITY_PATH" <<'PY'
import json
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
payout_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
wallet_dir = Path(sys.argv[4])
identity_dir = Path(sys.argv[5])
homelab_host = sys.argv[6]
api_url = sys.argv[7]
payout_url = sys.argv[8]
config_path = sys.argv[9]
identity_path = sys.argv[10]

status = json.loads(status_path.read_text(encoding="utf-8"))
payout = json.loads(payout_path.read_text(encoding="utf-8"))

secret_files = sorted(
    path.name for path in wallet_dir.iterdir()
    if path.is_file() and path.name != "manifest.json"
)
identity_files = sorted(path.name for path in identity_dir.iterdir() if path.is_file())

manifest = {
    "generatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "source": {
        "homelabHost": homelab_host,
        "apiUrl": api_url,
        "payoutUrl": payout_url,
        "configPath": config_path,
        "identityPath": identity_path,
    },
    "wallet": status.get("wallet"),
    "walletFeatures": status.get("walletFeatures") or [],
    "nodeID": status.get("nodeID"),
    "version": status.get("version"),
    "startedAt": status.get("startedAt"),
    "lastPinged": status.get("lastPinged"),
    "quicStatus": status.get("quicStatus"),
    "currentMonth": payout.get("currentMonth", {}),
    "previousMonth": payout.get("previousMonth", {}),
    "currentMonthExpectations": payout.get("currentMonthExpectations"),
    "custody": {
        "secretMaterialPresent": bool(secret_files),
        "secretFiles": secret_files,
    },
    "nodeIdentity": {
        "present": bool(identity_files),
        "files": identity_files,
    },
}

manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
}

# ── pré-checks ───────────────────────────────────────────────────────────────
mountpoint -q "$MOUNT_POINT" || die "Vault não montado. Execute: sudo ./vault-open.sh open"
[ "$(id -u)" -eq 0 ] || die "Execute como root: sudo $0"
ping -c1 -W3 "$HOMELAB_HOST" &>/dev/null || die "Homelab $HOMELAB_HOST inacessível"
ssh_run "true" || die "SSH para $HOMELAB_USER@$HOMELAB_HOST falhou"

mkdir -p "$BACKUP_ROOT"/{authentik,vaultwarden,bitwarden-cloud,storj}
mkdir -p "$STORJ_WALLET_DIR" "$STORJ_IDENTITY_DIR"
chown root:root "$STORJ_KEYS_ROOT" "$STORJ_WALLET_DIR" "$STORJ_IDENTITY_DIR"
chmod 700 "$STORJ_KEYS_ROOT" "$STORJ_WALLET_DIR" "$STORJ_IDENTITY_DIR"
log "=== BACKUP INICIADO — $DATE ==="
ERRORS=0

# ── 1. Authentik — PostgreSQL dump ────────────────────────────────────────────
log "[Authentik] Dump PostgreSQL (authentik-postgres)..."
DB_FILE="$BACKUP_ROOT/authentik/authentik-db-$DATE.sql.gz"

ssh_run "docker exec authentik-postgres pg_dump -U authentik authentik" \
    | gzip > "$DB_FILE" \
    && log "[Authentik] DB: $(du -sh "$DB_FILE" | cut -f1)" \
    || { log "[Authentik] ERRO: falha no pg_dump"; ERRORS=$((ERRORS+1)); }

# Manter apenas os últimos 7 dumps
trim_old_backups "$BACKUP_ROOT/authentik/authentik-db-*.sql.gz" 7

# ── 2. Authentik — media files ────────────────────────────────────────────────
log "[Authentik] Sincronizando media (/mnt/raid1/authentik/media)..."
rsync_run -az --delete \
    "$HOMELAB_USER@$HOMELAB_HOST:$AUTHENTIK_MEDIA_PATH/" \
    "$BACKUP_ROOT/authentik/media/" \
    && log "[Authentik] Media: $(du -sh "$BACKUP_ROOT/authentik/media" | cut -f1)" \
    || { log "[Authentik] ERRO: falha no rsync de media"; ERRORS=$((ERRORS+1)); }

# ── 3. Vaultwarden self-hosted — data dir ─────────────────────────────────────
log "[Vaultwarden] Sincronizando data dir..."
rsync_run -az --delete \
    "$HOMELAB_USER@$HOMELAB_HOST:$VAULTWARDEN_DATA_PATH/" \
    "$BACKUP_ROOT/vaultwarden/data/" \
    && log "[Vaultwarden] $(du -sh "$BACKUP_ROOT/vaultwarden/data" | cut -f1)" \
    || { log "[Vaultwarden] ERRO: falha no rsync"; ERRORS=$((ERRORS+1)); }

# ── 4. KuCoin API keys — snapshot do envfile ─────────────────────────────────
log "[KuCoin] Salvando API keys no vault..."
KUCOIN_VAULT_ENV="$MOUNT_POINT/keepass/kucoin.env"
KUCOIN_ENVFILE="/apps/crypto-trader/trading/btc_trading_agent/envfiles/BTC_USDT_aggressive.env"

ssh_run "grep -E '^KUCOIN_' $KUCOIN_ENVFILE 2>/dev/null" \
    > "$KUCOIN_VAULT_ENV" \
    && chmod 600 "$KUCOIN_VAULT_ENV" \
    && log "[KuCoin] keys salvas em keepass/kucoin.env" \
    || { log "[KuCoin] ERRO: não foi possível copiar as keys"; ERRORS=$((ERRORS+1)); }

# ── 5. Storj — wallet, identity e snapshots públicos ─────────────────────────
log "[Storj] Capturando snapshots do nó..."
STORJ_STATUS_FILE="$BACKUP_ROOT/storj/node-status-$DATE.json"
STORJ_PAYOUT_FILE="$BACKUP_ROOT/storj/payout-$DATE.json"
STORJ_CONFIG_FILE="$BACKUP_ROOT/storj/config-$DATE.yaml"
STORJ_MANIFEST_FILE="$STORJ_WALLET_DIR/manifest.json"

ssh_run "curl -fsS '$STORJ_API_URL'" > "$STORJ_STATUS_FILE" \
    && log "[Storj] Status salvo em backups/storj/$(basename "$STORJ_STATUS_FILE")" \
    || { log "[Storj] ERRO: falha ao capturar status do nó"; ERRORS=$((ERRORS+1)); }

ssh_run "curl -fsS '$STORJ_PAYOUT_URL'" > "$STORJ_PAYOUT_FILE" \
    && log "[Storj] Payout salvo em backups/storj/$(basename "$STORJ_PAYOUT_FILE")" \
    || { log "[Storj] ERRO: falha ao capturar payout do nó"; ERRORS=$((ERRORS+1)); }

rsync_run -az "$HOMELAB_USER@$HOMELAB_HOST:$STORJ_CONFIG_PATH" "$STORJ_CONFIG_FILE" \
    && log "[Storj] Config salvo em backups/storj/$(basename "$STORJ_CONFIG_FILE")" \
    || { log "[Storj] ERRO: falha ao copiar config.yaml"; ERRORS=$((ERRORS+1)); }

if rsync_run -az --delete \
    "$HOMELAB_USER@$HOMELAB_HOST:$STORJ_IDENTITY_PATH/" \
    "$STORJ_IDENTITY_DIR/"; then
    chown root:root "$STORJ_IDENTITY_DIR" "$STORJ_IDENTITY_DIR"/* 2>/dev/null || true
    chmod 700 "$STORJ_IDENTITY_DIR"
    chmod 600 "$STORJ_IDENTITY_DIR"/* 2>/dev/null || true
    if find "$STORJ_IDENTITY_DIR" -mindepth 1 -maxdepth 1 -type f | grep -q .; then
        log "[Storj] Identity sincronizada em keys/storj/identity"
    else
        log "[Storj] AVISO: identity do nó veio vazia"
        ERRORS=$((ERRORS+1))
    fi
else
    log "[Storj] ERRO: falha ao sincronizar identity do nó"
    ERRORS=$((ERRORS+1))
fi

copy_optional_secret "keystore" "$STORJ_WALLET_KEYSTORE_FILE" "$STORJ_WALLET_KEYSTORE_REMOTE_FILE" "$STORJ_WALLET_DIR/keystore.json" || true
copy_optional_secret "private key" "$STORJ_WALLET_PRIVATE_KEY_FILE" "$STORJ_WALLET_PRIVATE_KEY_REMOTE_FILE" "$STORJ_WALLET_DIR/private-key.txt" || true
copy_optional_secret "mnemonic" "$STORJ_WALLET_MNEMONIC_FILE" "$STORJ_WALLET_MNEMONIC_REMOTE_FILE" "$STORJ_WALLET_DIR/mnemonic.txt" || true

if [ -f "$STORJ_STATUS_FILE" ] && [ -f "$STORJ_PAYOUT_FILE" ]; then
    write_storj_manifest "$STORJ_STATUS_FILE" "$STORJ_PAYOUT_FILE" "$STORJ_MANIFEST_FILE" \
        && chmod 600 "$STORJ_MANIFEST_FILE" \
        && log "[Storj] Manifesto atualizado em keys/storj/wallet/manifest.json" \
        || { log "[Storj] ERRO: falha ao gerar manifesto"; ERRORS=$((ERRORS+1)); }
fi

trim_old_backups "$BACKUP_ROOT/storj/node-status-*.json" 10
trim_old_backups "$BACKUP_ROOT/storj/payout-*.json" 10
trim_old_backups "$BACKUP_ROOT/storj/config-*.yaml" 10

# ── 6. Bitwarden cloud — export JSON cifrado ──────────────────────────────────
log "[Bitwarden cloud] Exportando vault (edenilson.teixeira@rpa4all.com)..."
BW_EXPORT_FILE="$BACKUP_ROOT/bitwarden-cloud/bw-export-$DATE.json"

# Verifica se bw CLI está disponível no homelab
if ssh_run "command -v bw &>/dev/null || /snap/bin/bw version &>/dev/null"; then
    BW_BIN=$(ssh_run "command -v bw 2>/dev/null || echo /snap/bin/bw")

    # Verifica se há sessão ativa
    BW_STATUS=$(ssh_run "BW_SESSION=\${BW_SESSION:-} $BW_BIN status 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"status\"])'" 2>/dev/null || echo "unauthenticated")

    if [ "$BW_STATUS" = "unlocked" ]; then
        ssh_run "BW_SESSION=\${BW_SESSION:-} $BW_BIN export --format json --raw" \
            > "$BW_EXPORT_FILE" \
            && log "[Bitwarden cloud] Export: $(du -sh "$BW_EXPORT_FILE" | cut -f1)" \
            || { log "[Bitwarden cloud] ERRO no export"; ERRORS=$((ERRORS+1)); }

        # Manter apenas os últimos 5 exports
        trim_old_backups "$BACKUP_ROOT/bitwarden-cloud/bw-export-*.json" 5
    else
        log "[Bitwarden cloud] AVISO: sessão bw não está desbloqueada (status: $BW_STATUS)"
        log "[Bitwarden cloud] Para habilitar, no homelab:"
        log "  export BW_SESSION=\$(bw unlock --passwordenv BW_PASSWORD --raw)"
        log "  sudo -E ./backup-to-vault.sh"
        ERRORS=$((ERRORS+1))
    fi
else
    log "[Bitwarden cloud] AVISO: bw CLI não encontrado no homelab"
    ERRORS=$((ERRORS+1))
fi

# ── resumo ────────────────────────────────────────────────────────────────────
log ""
log "=== BACKUP CONCLUÍDO (erros/avisos: $ERRORS) ==="
df -h "$MOUNT_POINT" | grep -v Filesystem | tee -a "$LOG"
echo ""
du -sh "$BACKUP_ROOT"/*/  2>/dev/null | tee -a "$LOG"
echo ""
if [ "$ERRORS" -eq 0 ]; then
    STATUS_MSG="Vault backup OK — Authentik + Vaultwarden + Bitwarden cloud + KuCoin + Storj"
    log "Status: OK"
else
    STATUS_MSG="Vault backup concluído com $ERRORS aviso(s) — verifique o log"
    log "Status: $ERRORS aviso(s) — verifique $LOG"
fi

# Notificação Telegram — credenciais via /home/homelab/myClaude/.env no homelab
TBOT_TOKEN=$(ssh_run "grep TELEGRAM_BOT_TOKEN /home/homelab/myClaude/.env 2>/dev/null | cut -d= -f2" || true)
TBOT_CHAT=$(ssh_run "grep TELEGRAM_CHAT_ID /home/homelab/myClaude/.env 2>/dev/null | cut -d= -f2" || true)

if [ -n "$TBOT_TOKEN" ] && [ -n "$TBOT_CHAT" ]; then
    SPACE_USED=$(df -h "$MOUNT_POINT" | awk 'NR==2{print $3"/"$2}')
    TBOT_MSG="${STATUS_MSG}
Data: ${DATE} | Espaço: ${SPACE_USED}"
    curl -s "https://api.telegram.org/bot${TBOT_TOKEN}/sendMessage" \
        -d "chat_id=${TBOT_CHAT}" \
        --data-urlencode "text=${TBOT_MSG}" \
        -o /dev/null || true
    log "Notificação Telegram enviada"
else
    log "Telegram: credenciais não encontradas, pulando notificação"
fi
