#!/usr/bin/env bash
# Importa um secret do Bitwarden para o Authentik (via Secrets Agent).
#
# Por que existe: credenciais no homelab devem vir do Authentik, não de
# arquivos soltos (credentials.json, token.pickle, Environment= inline em
# unit systemd). Este script move um item que já está no cofre do Bitwarden
# para o Authentik, no formato `<nome>#<campo>` que o Secrets Agent expõe.
#
# A senha mestra do Bitwarden é digitada POR VOCÊ, no seu terminal, e nunca
# aparece em log, histórico de comando ou saída. Os valores dos secrets também
# nunca são impressos — só o comprimento, pra você conferir que não veio vazio.
#
# Pré-requisito: SECRETS_AGENT_API_KEY no ambiente (fonte canônica:
# ~/.config/homelab/secrets.env, fora do git):
#   set -a; source ~/.config/homelab/secrets.env; set +a
#
# Uso:
#   # 1) destravar o cofre (senha fica só no seu terminal)
#   export BW_SESSION=$(bw unlock --raw)
#
#   # 2) achar o item (imprime só nomes, nunca valores)
#   scripts/import_bw_secret_to_authentik.sh --search google
#
#   # 3) importar campos do item para o Authentik
#   scripts/import_bw_secret_to_authentik.sh \
#       --item "<nome ou id do item no bw>" \
#       --target google/oauth_client_installed \
#       --map username=client_id --map password=client_secret
#
# Campos de origem aceitos em --map: username, password, notes, ou
# custom:<nome-do-campo-customizado>.
set -uo pipefail

SECRETS_AGENT_URL="${SECRETS_AGENT_URL:-http://localhost:8088}"

die() { echo "ERRO: $*" >&2; exit 1; }

command -v bw >/dev/null || die "bw (Bitwarden CLI) não encontrado."
command -v jq >/dev/null || die "jq não encontrado (apt install jq)."

[[ -n "${BW_SESSION:-}" ]] || die "BW_SESSION não definido. Rode antes: export BW_SESSION=\$(bw unlock --raw)"

# A chave nunca fica em código/repo (público) — vem do ambiente, cuja fonte
# canônica é ~/.config/homelab/secrets.env (0600, fora do git).
[[ -n "${SECRETS_AGENT_API_KEY:-}" ]] || die \
  "SECRETS_AGENT_API_KEY ausente do ambiente. Rode: set -a; source ~/.config/homelab/secrets.env; set +a"

MODE=""; ITEM=""; TARGET=""; declare -a MAPS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --search) MODE="search"; ITEM="${2:-}"; shift 2 ;;
    --item)   ITEM="${2:-}"; shift 2 ;;
    --target) TARGET="${2:-}"; shift 2 ;;
    --map)    MAPS+=("${2:-}"); shift 2 ;;
    *) die "argumento desconhecido: $1" ;;
  esac
done

if [[ "$MODE" == "search" ]]; then
  echo "Itens no Bitwarden que casam com '$ITEM' (só nomes, sem valores):"
  bw list items --search "$ITEM" --session "$BW_SESSION" 2>/dev/null \
    | jq -r '.[] | "  \(.name)   [id=\(.id)]"' \
    || die "falha ao listar itens (cofre destravado?)"
  exit 0
fi

[[ -n "$ITEM"   ]] || die "--item é obrigatório."
[[ -n "$TARGET" ]] || die "--target é obrigatório (ex: google/oauth_client_installed)."
[[ ${#MAPS[@]} -gt 0 ]] || die "pelo menos um --map origem=destino é obrigatório."

RAW="$(bw get item "$ITEM" --session "$BW_SESSION" 2>/dev/null)" \
  || die "item '$ITEM' não encontrado no Bitwarden."

for m in "${MAPS[@]}"; do
  src="${m%%=*}"; dst="${m#*=}"
  [[ "$src" != "$m" ]] || die "--map inválido: '$m' (use origem=destino)"

  case "$src" in
    username) val="$(jq -r '.login.username // empty' <<<"$RAW")" ;;
    password) val="$(jq -r '.login.password // empty' <<<"$RAW")" ;;
    notes)    val="$(jq -r '.notes // empty'          <<<"$RAW")" ;;
    custom:*) val="$(jq -r --arg n "${src#custom:}" '.fields[]? | select(.name==$n) | .value // empty' <<<"$RAW")" ;;
    *) die "origem desconhecida em --map: '$src'" ;;
  esac

  if [[ -z "$val" ]]; then
    echo "  ⚠ $src → $dst: VAZIO no Bitwarden, pulando (nada foi gravado)."
    continue
  fi

  # --data-binary @- : o valor vai pelo stdin, não pela linha de comando
  # (não aparece em `ps`, histórico, nem no log de auditoria do agent).
  resp="$(jq -nc --arg name "$TARGET" --arg field "$dst" --arg value "$val" \
            --arg notes "importado do Bitwarden" \
            '{name:$name, field:$field, value:$value, notes:$notes}' \
          | curl -s -X POST "$SECRETS_AGENT_URL/secrets" \
              -H "X-API-KEY: $SECRETS_AGENT_API_KEY" -H 'Content-Type: application/json' \
              --data-binary @- 2>/dev/null)"

  status="$(jq -r '.status // "erro"' <<<"$resp" 2>/dev/null || echo erro)"
  ak_ok="$(jq -r '.backend_sync.ok // false' <<<"$resp" 2>/dev/null || echo false)"
  if [[ "$status" == "stored" ]]; then
    echo "  ✅ $src → ${TARGET}#${dst} (${#val} chars) | authentik=${ak_ok}"
  else
    echo "  ❌ $src → ${TARGET}#${dst} falhou: $(jq -r '.detail // .' <<<"$resp" 2>/dev/null | head -c 200)"
  fi
  unset val
done

echo
echo "Conferir (mostra só o comprimento, nunca o valor):"
echo "  curl -s -H \"X-API-KEY: \$SECRETS_AGENT_API_KEY\" \\"
echo "    \"$SECRETS_AGENT_URL/secrets/local/$TARGET?field=<campo>\" | jq '.value | length'"
