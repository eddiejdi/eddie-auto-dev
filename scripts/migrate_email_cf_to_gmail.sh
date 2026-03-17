#!/usr/bin/env bash
# ============================================================================
# Migração de Email: Cloudflare Email Routing → Gmail (Google Workspace)
# Domínio: rpa4all.com
#
# Este script:
# 1. Lista todos os DNS records atuais (backup)
# 2. Remove MX e TXT records do Cloudflare Email Routing
# 3. Adiciona MX records do Gmail/Google Workspace
# 4. Adiciona SPF, DKIM e DMARC records para Gmail
# 5. NÃO TOCA em records A/AAAA/CNAME (HTTP/tunnel continuam funcionando)
#
# Uso:
#   export CF_TOKEN="seu_token_aqui"
#   bash scripts/migrate_email_cf_to_gmail.sh [--dry-run]
#
# Requisitos:
#   - CF_TOKEN: Cloudflare Global API Key ou API Token com permissão DNS Edit
#   - CF_EMAIL: Email da conta Cloudflare (para Global API Key)
#   - curl, jq
# ============================================================================

set -euo pipefail

# --- Configuração ---
DOMAIN="rpa4all.com"
CF_EMAIL="${CF_EMAIL:-edenilson.teixeira@rpa4all.com}"
CF_TOKEN="${CF_TOKEN:-}"
DRY_RUN=false

# Google Workspace DKIM — gerado em admin.google.com → Apps → Gmail → Autenticar email
GOOGLE_DKIM_VALUE="${GOOGLE_DKIM_VALUE:-v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAltBDfuvEUrOvIcJGx56k5kum1YJOqz2njaVLtefOfySFZNwg4s3c3vb29AKTDY2lJXWEQ/bT1JrcfPo/NkP0eje9gstxf/y/siejVypiqUaratbm0HSz/K1PNS1vxJSxJsPnbF5wlM9tBXVly5XgY8ndMY/3s1wfgdstN9BBYKTt/FyVK0JZ0gcv1bE19WRVPgPhN4E8rQtI7K5QV2gXwQdO7t7EhnS9r+avVf62XURRU0mh/anMDgVZMQenKGLep5L0sfOxnj6Sa9Jd48PWVdq1cWICBvD6s3MHd4PeQerlhNBWQhqhez6MK5KyE4nd7lrNjlAgVzauvEQIwH5D9wIDAQAB}"

# --- Parse args ---
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --help|-h)
            echo "Uso: $0 [--dry-run]"
            echo "  --dry-run: Apenas mostra o que seria feito, sem executar"
            exit 0
            ;;
    esac
done

# --- Validações ---
if [[ -z "$CF_TOKEN" ]]; then
    echo "❌ CF_TOKEN não definido. Execute: export CF_TOKEN='seu_token'"
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo "❌ jq não instalado. Instale com: sudo apt install jq"
    exit 1
fi

# --- Funções helpers ---
cf_api() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    local args=(
        -s
        -X "$method"
        -H "Authorization: Bearer $CF_TOKEN"
        -H "Content-Type: application/json"
    )

    if [[ -n "$data" ]]; then
        args+=(-d "$data")
    fi

    curl "${args[@]}" "https://api.cloudflare.com/client/v4${endpoint}"
}

log() { echo "[$(date '+%H:%M:%S')] $*"; }
warn() { echo "[$(date '+%H:%M:%S')] ⚠️  $*"; }
ok() { echo "[$(date '+%H:%M:%S')] ✅ $*"; }
err() { echo "[$(date '+%H:%M:%S')] ❌ $*"; }

# --- 1. Obter Zone ID ---
log "Obtendo Zone ID para $DOMAIN..."
ZONE_RESPONSE=$(cf_api GET "/zones?name=$DOMAIN")
ZONE_ID=$(echo "$ZONE_RESPONSE" | jq -r '.result[0].id // empty')

if [[ -z "$ZONE_ID" ]]; then
    err "Não foi possível obter Zone ID para $DOMAIN"
    echo "$ZONE_RESPONSE" | jq .
    exit 1
fi
ok "Zone ID: $ZONE_ID"

# --- 2. Backup de TODOS os DNS records ---
log "Fazendo backup dos DNS records..."
BACKUP_FILE="/tmp/cf_dns_backup_${DOMAIN}_$(date '+%Y%m%d_%H%M%S').json"
ALL_RECORDS=$(cf_api GET "/zones/$ZONE_ID/dns_records?per_page=100")
echo "$ALL_RECORDS" | jq '.' > "$BACKUP_FILE"
ok "Backup salvo em: $BACKUP_FILE"

# Mostrar resumo
echo ""
echo "=== DNS Records Atuais ==="
echo "$ALL_RECORDS" | jq -r '.result[] | "\(.type)\t\(.name)\t\(.content)"' | sort
echo ""

# --- 3. Identificar records de email do Cloudflare para remover ---
log "Identificando records de email do Cloudflare..."

# MX records apontando para Cloudflare Email Routing
CF_MX_IDS=$(echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="MX" and (.content | test("route[0-9]*\\.mx\\.cloudflare\\.net|mx\\.cloudflare\\.net|cloudflare"; "i"))) | .id')

# SPF record com include:_spf.mx.cloudflare.net
CF_SPF_IDS=$(echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="TXT" and (.content | test("spf.*cloudflare|cloudflare.*spf"; "i"))) | .id')

# Cloudflare verification TXT records
CF_VERIFY_IDS=$(echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="TXT" and (.content | test("cloudflare-verify|cf-verify"; "i"))) | .id')

echo ""
echo "=== Records de Email Cloudflare encontrados ==="
echo "MX records Cloudflare:"
echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="MX" and (.content | test("route[0-9]*\\.mx\\.cloudflare\\.net|mx\\.cloudflare\\.net|cloudflare"; "i"))) | "  \(.id) → \(.content) (pri: \(.priority))"'
echo ""
echo "SPF records com Cloudflare:"
echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="TXT" and (.content | test("spf.*cloudflare|cloudflare.*spf"; "i"))) | "  \(.id) → \(.content)"'
echo ""
echo "Verification TXT:"
echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="TXT" and (.content | test("cloudflare-verify|cf-verify"; "i"))) | "  \(.id) → \(.content)"'
echo ""

# Também listar MX records existentes que NÃO são Cloudflare (para não apagar)
echo "Outros MX records (manter):"
echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="MX" and (.content | test("cloudflare"; "i") | not)) | "  \(.id) → \(.content) (pri: \(.priority))"'
echo ""

# Listar registros que NÃO serão tocados
echo "=== Records que NÃO serão alterados (HTTP/tunnel/outros) ==="
echo "$ALL_RECORDS" | jq -r '.result[] | select(.type=="A" or .type=="AAAA" or .type=="CNAME" or .type=="SRV") | "\(.type)\t\(.name)\t\(.content)\t(proxied: \(.proxied))"' | sort
echo ""

if $DRY_RUN; then
    echo "=== 🔍 DRY RUN — Nenhuma alteração será feita ==="
    echo ""
    echo "Ações que seriam executadas:"
    echo "  1. Remover MX records Cloudflare: $(echo "$CF_MX_IDS" | wc -w) record(s)"
    echo "  2. Remover SPF com Cloudflare: $(echo "$CF_SPF_IDS" | wc -w) record(s)"
    echo "  3. Remover TXT verification: $(echo "$CF_VERIFY_IDS" | wc -w) record(s)"
    echo "  4. Adicionar 5 MX records do Gmail"
    echo "  5. Adicionar SPF record para Gmail"
    echo "  6. Adicionar DMARC record"
    echo "  7. Adicionar DKIM record (se valor fornecido)"
    echo ""
    echo "Para executar de verdade, rode sem --dry-run"
    exit 0
fi

# --- Confirmação ---
echo "⚠️  ATENÇÃO: Este script vai:"
echo "  1. REMOVER os MX records do Cloudflare Email Routing"
echo "  2. REMOVER o SPF com referência ao Cloudflare"
echo "  3. ADICIONAR MX records do Gmail/Google Workspace"
echo "  4. ADICIONAR SPF/DMARC/DKIM para Gmail"
echo "  5. NÃO vai tocar em records A/AAAA/CNAME (HTTP continua)"
echo ""
echo "Backup salvo em: $BACKUP_FILE"
echo ""
read -r -p "Confirma? (sim/não): " CONFIRM
if [[ "$CONFIRM" != "sim" ]]; then
    echo "Cancelado."
    exit 0
fi

# --- 4. Remover MX records do Cloudflare ---
log "Removendo MX records do Cloudflare Email Routing..."
for id in $CF_MX_IDS; do
    if [[ -n "$id" ]]; then
        RESULT=$(cf_api DELETE "/zones/$ZONE_ID/dns_records/$id")
        SUCCESS=$(echo "$RESULT" | jq -r '.success')
        if [[ "$SUCCESS" == "true" ]]; then
            ok "MX record removido: $id"
        else
            err "Falha ao remover MX $id: $(echo "$RESULT" | jq -r '.errors')"
        fi
    fi
done

# --- 5. Remover SPF com Cloudflare ---
log "Removendo SPF records com referência Cloudflare..."
for id in $CF_SPF_IDS; do
    if [[ -n "$id" ]]; then
        RESULT=$(cf_api DELETE "/zones/$ZONE_ID/dns_records/$id")
        SUCCESS=$(echo "$RESULT" | jq -r '.success')
        if [[ "$SUCCESS" == "true" ]]; then
            ok "SPF record removido: $id"
        else
            err "Falha ao remover SPF $id: $(echo "$RESULT" | jq -r '.errors')"
        fi
    fi
done

# --- 6. Remover TXT verification do Cloudflare ---
log "Removendo TXT verification records do Cloudflare..."
for id in $CF_VERIFY_IDS; do
    if [[ -n "$id" ]]; then
        RESULT=$(cf_api DELETE "/zones/$ZONE_ID/dns_records/$id")
        SUCCESS=$(echo "$RESULT" | jq -r '.success')
        if [[ "$SUCCESS" == "true" ]]; then
            ok "TXT verification removido: $id"
        else
            err "Falha ao remover TXT $id: $(echo "$RESULT" | jq -r '.errors')"
        fi
    fi
done

# --- 7. Adicionar MX records do Gmail/Google Workspace ---
log "Adicionando MX records do Gmail..."

GMAIL_MX_RECORDS=(
    '{"type":"MX","name":"'"$DOMAIN"'","content":"aspmx.l.google.com","priority":1,"ttl":3600}'
    '{"type":"MX","name":"'"$DOMAIN"'","content":"alt1.aspmx.l.google.com","priority":5,"ttl":3600}'
    '{"type":"MX","name":"'"$DOMAIN"'","content":"alt2.aspmx.l.google.com","priority":5,"ttl":3600}'
    '{"type":"MX","name":"'"$DOMAIN"'","content":"alt3.aspmx.l.google.com","priority":10,"ttl":3600}'
    '{"type":"MX","name":"'"$DOMAIN"'","content":"alt4.aspmx.l.google.com","priority":10,"ttl":3600}'
)

for mx_data in "${GMAIL_MX_RECORDS[@]}"; do
    RESULT=$(cf_api POST "/zones/$ZONE_ID/dns_records" "$mx_data")
    SUCCESS=$(echo "$RESULT" | jq -r '.success')
    CONTENT=$(echo "$mx_data" | jq -r '.content')
    PRIORITY=$(echo "$mx_data" | jq -r '.priority')
    if [[ "$SUCCESS" == "true" ]]; then
        ok "MX adicionado: $CONTENT (prioridade $PRIORITY)"
    else
        err "Falha ao adicionar MX $CONTENT: $(echo "$RESULT" | jq -r '.errors')"
    fi
done

# --- 8. Adicionar SPF para Gmail ---
log "Adicionando SPF record para Gmail..."
SPF_DATA='{"type":"TXT","name":"'"$DOMAIN"'","content":"v=spf1 include:_spf.google.com ~all","ttl":3600}'
RESULT=$(cf_api POST "/zones/$ZONE_ID/dns_records" "$SPF_DATA")
SUCCESS=$(echo "$RESULT" | jq -r '.success')
if [[ "$SUCCESS" == "true" ]]; then
    ok "SPF record adicionado: v=spf1 include:_spf.google.com ~all"
else
    err "Falha ao adicionar SPF: $(echo "$RESULT" | jq -r '.errors')"
fi

# --- 9. Adicionar DMARC ---
log "Adicionando DMARC record..."
DMARC_DATA='{"type":"TXT","name":"_dmarc.'"$DOMAIN"'","content":"v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@'"$DOMAIN"'; pct=100","ttl":3600}'
RESULT=$(cf_api POST "/zones/$ZONE_ID/dns_records" "$DMARC_DATA")
SUCCESS=$(echo "$RESULT" | jq -r '.success')
if [[ "$SUCCESS" == "true" ]]; then
    ok "DMARC record adicionado"
else
    # Pode já existir
    warn "DMARC pode já existir: $(echo "$RESULT" | jq -r '.errors')"
fi

# --- 10. Adicionar DKIM (se valor fornecido) ---
if [[ "$GOOGLE_DKIM_VALUE" != "SUBSTITUIR_PELO_VALOR_DKIM_DO_GOOGLE_ADMIN" ]]; then
    log "Adicionando DKIM record..."
    DKIM_DATA='{"type":"TXT","name":"google._domainkey.'"$DOMAIN"'","content":"'"$GOOGLE_DKIM_VALUE"'","ttl":3600}'
    RESULT=$(cf_api POST "/zones/$ZONE_ID/dns_records" "$DKIM_DATA")
    SUCCESS=$(echo "$RESULT" | jq -r '.success')
    if [[ "$SUCCESS" == "true" ]]; then
        ok "DKIM record adicionado"
    else
        err "Falha ao adicionar DKIM: $(echo "$RESULT" | jq -r '.errors')"
    fi
else
    warn "DKIM não configurado — valor placeholder detectado"
    echo ""
    echo "📋 Para configurar DKIM:"
    echo "   1. Acesse admin.google.com"
    echo "   2. Vá em Apps → Google Workspace → Gmail → Autenticar email"
    echo "   3. Clique em 'Gerar novo registro' para o domínio $DOMAIN"
    echo "   4. Copie o valor TXT gerado"
    echo "   5. Execute:"
    echo "      export GOOGLE_DKIM_VALUE='v=DKIM1; k=rsa; p=SUA_CHAVE_AQUI'"
    echo "      # E adicione manualmente:"
    echo "      curl -s -X POST 'https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records' \\"
    echo "        -H 'X-Auth-Email: $CF_EMAIL' -H 'X-Auth-Key: \$CF_TOKEN' \\"
    echo "        -H 'Content-Type: application/json' \\"
    echo "        -d '{\"type\":\"TXT\",\"name\":\"google._domainkey.$DOMAIN\",\"content\":\"'\"\$GOOGLE_DKIM_VALUE\"'\",\"ttl\":3600}'"
    echo ""
fi

# --- 11. Verificação final ---
echo ""
log "=== Verificação Final ==="
echo ""

# Listar novos records
FINAL_RECORDS=$(cf_api GET "/zones/$ZONE_ID/dns_records?per_page=100")

echo "=== MX Records (deve mostrar Gmail) ==="
echo "$FINAL_RECORDS" | jq -r '.result[] | select(.type=="MX") | "  \(.content) (pri: \(.priority))"' | sort -t: -k2 -n
echo ""

echo "=== SPF Record ==="
echo "$FINAL_RECORDS" | jq -r '.result[] | select(.type=="TXT" and (.content | test("spf"; "i"))) | "  \(.content)"'
echo ""

echo "=== DMARC Record ==="
echo "$FINAL_RECORDS" | jq -r '.result[] | select(.type=="TXT" and (.name | test("_dmarc"))) | "  \(.content)"'
echo ""

echo "=== DKIM Record ==="
echo "$FINAL_RECORDS" | jq -r '.result[] | select(.type=="TXT" and (.name | test("_domainkey"))) | "  \(.name) → \(.content[:60])..."'
echo ""

echo "=== Records HTTP/Tunnel (devem estar intactos) ==="
echo "$FINAL_RECORDS" | jq -r '.result[] | select(.type=="A" or .type=="AAAA" or .type=="CNAME") | "  \(.type)\t\(.name)\t\(.content)\t(proxied: \(.proxied))"' | sort
echo ""

ok "Migração concluída!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "   1. Desabilitar Email Routing no dashboard Cloudflare:"
echo "      → dash.cloudflare.com → $DOMAIN → Email → Email Routing → Desabilitar"
echo "   2. Configurar DKIM no admin.google.com (se ainda não fez)"
echo "   3. Testar envio/recebimento de email"
echo "   4. Verificar MX com: dig MX $DOMAIN +short"
echo "   5. Verificar SPF com: dig TXT $DOMAIN +short"
echo ""
echo "🔍 Para validar online: https://toolbox.googleapps.com/apps/checkmx/check?domain=$DOMAIN"
