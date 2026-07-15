#!/usr/bin/env bash
# Instala o pre-commit gate de variáveis no checkout local.
# git não versiona .git/hooks/, então cada clone precisa rodar isto uma vez
# (mesmo padrão do symlink usado para o Grok em scripts/install_grok_hooks.sh).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${REPO_ROOT}/scripts/git-hooks/pre-commit"
DST="${REPO_ROOT}/.git/hooks/pre-commit"

if [[ -e "${DST}" && ! -L "${DST}" ]]; then
  echo "⚠️  ${DST} já existe e não é um symlink — backup em pre-commit.bak antes de sobrescrever." >&2
  mv "${DST}" "${DST}.bak"
fi

ln -sfn "${SRC}" "${DST}"
chmod +x "${SRC}"

echo "✅ pre-commit instalado: ${DST} -> ${SRC}"
echo "   Valida taxonomia de variáveis antes de cada commit (tools/hooks/variable_registry_validate.py)."
