#!/bin/bash
# Helper: cria o item do PostgreSQL no Bitwarden a partir do JSON local
set -e
if ! command -v bw >/dev/null 2>&1; then
  echo "bw CLI não encontrado. Instale ou execute manualmente em outra máquina."
  exit 1
fi
if ! bw login --check >/dev/null 2>&1; then
  echo "Por favor, execute: bw login e depois bw unlock --raw (ou exporte BW_SESSION)."
  exit 1
fi
export BW_SESSION=$(bw unlock --raw)
ITEM_JSON_FILE="$(dirname "$0")/eddie_postgres_item.json"
if [ ! -f "$ITEM_JSON_FILE" ]; then
  echo "Arquivo $ITEM_JSON_FILE não encontrado"
  exit 1
fi
echo "Criando item no Bitwarden a partir de $ITEM_JSON_FILE..."
ITEM_ID=$(bw encode < "$ITEM_JSON_FILE" | bw create item | jq -r '.id')
if [ -n "$ITEM_ID" ] && [ "$ITEM_ID" != "null" ]; then
  echo "Item criado com ID: $ITEM_ID"
  bw sync
  echo "Sincronizado. Limpando sessão local.";
  unset BW_SESSION
  exit 0
else
  echo "Falha ao criar item. Saída do bw create:"
  bw encode < "$ITEM_JSON_FILE" | bw create item || true
  exit 2
fi
