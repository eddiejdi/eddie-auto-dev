#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Uso: $0 <username>"
  exit 1
fi
USER="$1"

echo "Verificando identidade via NSS/SSSD:"
getent passwd "$USER" || { echo "Usuário não encontrado via getent"; exit 2; }

echo "Testando montagem automática (autofs):"
ls -ld "/home/$USER" || echo "/home/$USER não montado (ainda) — tente login para montar."

echo "Se o diretório existir e contiver arquivos, a montagem e profile funcionaram." 
