#!/usr/bin/env bash
set -euo pipefail

# migrate_secrets_to_bw.sh
# Uso: ./migrate_secrets_to_bw.sh [--apply] [file1 file2 ...]
# - Sem --apply: faz dry-run e imprime comandos recomendados
# - Com --apply: tenta criar itens no Bitwarden (requer bw CLI e sessão BW_SESSION)

DRY_RUN=1
FILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=0; shift ;;
    --help) echo "Usage: $0 [--apply] [files...]"; exit 0 ;;
    *) FILES+=("$1"); shift ;;
  esac
done

if ! command -v bw >/dev/null 2>&1; then
  echo "Erro: bw (Bitwarden CLI) não encontrado. Instale: https://bitwarden.com/help/cli/" >&2
  exit 2
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  # sensible defaults to check common local secret paths
  FILES=("$HOME/.secrets/.env.jira" "$HOME/.secrets/.env" ".env")
fi

echo "Bitwarden migration helper"
echo "Dry-run: $([[ $DRY_RUN -eq 1 ]] && echo yes || echo no)"

if [[ $DRY_RUN -eq 0 ]]; then
  if [[ -z "${BW_SESSION:-}" ]]; then
    # Tentar ler de arquivo como fallback
    if [[ -f /tmp/bw_session.txt ]]; then
      BW_SESSION="$(cat /tmp/bw_session.txt)"
    else
      echo "Para --apply é necessário desbloquear a sessão do bw. Execute: 'bw unlock' e exporte BW_SESSION." >&2
      exit 3
    fi
  fi
fi

for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "Arquivo não encontrado: $f — pulando"
    continue
  fi

  echo "Processando $f"
  name_base=$(basename "$f")

  # read key=value lines and create a secure note per key
  while IFS= read -r line || [[ -n $line ]]; do
    # skip comments and blank lines
    [[ "$line" =~ ^# ]] && continue
    [[ -z "$line" ]] && continue
    
    if [[ "$line" != *=* ]]; then
      # store entire line as note
      note_name="$name_base:line"
      note_value="$line"
    else
      key=${line%%=*}
      val=${line#*=}
      note_name="$name_base:$key"
      note_value="$val"
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
      echo "DRY: criar item '$note_name' com valor (length: ${#note_value})"
    else
      # Usar jq para construir JSON válido com escape correto
      payload=$(jq -n \
        --arg type "3" \
        --arg name "$note_name" \
        --arg notes "$note_value" \
        '{type: ($type | tonumber), name: $name, notes: $notes}')
      echo "Criando item: $note_name"
      if bw create item "$payload" --session "$BW_SESSION" >/dev/null 2>&1; then
        echo "✓ Item criado com sucesso"
      else
        echo "✗ Erro ao criar item"
      fi
    fi

  done < "$f"

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "Sugestão: após verificar a saída, rode:\n  ./migrate_secrets_to_bw.sh --apply $f\nE então remova/arquive o arquivo local com cuidado."
  else
    echo "Arquivo $f migrado (ou items criados). Considere remover o arquivo local com segurança." 
  fi
done

echo "Concluído. Lembre-se de não commitar secrets no repo."
