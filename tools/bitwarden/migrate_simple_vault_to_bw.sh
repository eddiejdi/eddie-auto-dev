#!/usr/bin/env bash
set -euo pipefail

SECRETS_DIR="tools/simple_vault/secrets"
if [ ! -d "$SECRETS_DIR" ]; then
  echo "Diretório $SECRETS_DIR não encontrado"
  exit 1
fi

if ! command -v bw >/dev/null 2>&1; then
  echo "Erro: bw CLI não encontrado"
  exit 1
fi

# Ensure bw logged in
if ! bw login --check >/dev/null 2>&1; then
  echo "Por favor, faça login no Bitwarden antes: bw login"
  exit 1
fi

# Unlock BW interactively
echo "Desbloqueando Bitwarden (será solicitado master password)..."
export BW_SESSION=$(bw unlock --raw)

# Determine passphrase file
PASSFILE="${SIMPLE_VAULT_PASSPHRASE_FILE:-}"
if [ -n "$PASSFILE" ] && [ -f "$PASSFILE" ]; then
  echo "Usando SIMPLE_VAULT_PASSPHRASE_FILE=$PASSFILE"
else
  read -rp "Caminho para SIMPLE_VAULT_PASSPHRASE_FILE (ou ENTER para inserir passphrase interativa): " PASSFILE_INPUT
  if [ -n "$PASSFILE_INPUT" ] && [ -f "$PASSFILE_INPUT" ]; then
    PASSFILE="$PASSFILE_INPUT"
  else
    echo "Será solicitada a passphrase para cada arquivo .gpg via stdin (use com cuidado)."
    PASSFILE=""
  fi
fi

for f in "$SECRETS_DIR"/*; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  name_noext="${base%.*}"
  echo "Migrando: $base -> Bitwarden item: simple_vault/$name_noext"

  tmpfile=$(mktemp)
  if [[ "$f" == *.gpg ]]; then
    if [ -n "$PASSFILE" ]; then
      gpg --batch --quiet --yes --pinentry-mode loopback --passphrase-file "$PASSFILE" -o "$tmpfile" -d "$f" || { echo "Falha ao decifrar $f"; rm -f "$tmpfile"; continue; }
    else
      echo "Digite a passphrase para $base:";
      read -s pass
      echo
      gpg --batch --quiet --yes --pinentry-mode loopback --passphrase "$pass" -o "$tmpfile" -d "$f" || { echo "Falha ao decifrar $f"; rm -f "$tmpfile"; continue; }
    fi
  else
    # plaintext
    cp "$f" "$tmpfile"
  fi

  # Read content
  content=$(sed -n '1,20000p' "$tmpfile") || content=""

  # Build JSON safely with jq
  item_json=$(jq -n --arg name "simple_vault/$name_noext" --arg notes "$content" '{organizationId:null, folderId:null, type:1, name:$name, notes:$notes, favorite:false}')

  echo "$item_json" | bw encode | bw create item >/dev/null || { echo "Erro ao criar item no BW para $name_noext"; rm -f "$tmpfile"; continue; }
  echo "Criado: simple_vault/$name_noext"
  rm -f "$tmpfile"
done

# Sync and cleanup
bw sync >/dev/null || true
unset BW_SESSION

echo "Migração concluída. Verifique no Bitwarden os itens com prefixo 'simple_vault/'." 
