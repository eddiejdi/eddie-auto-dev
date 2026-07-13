#!/usr/bin/env bash
# Instala hooks do Claude Code no Grok Build via symlink global.
# Hooks de projeto (.grok/hooks/) exigem trust; o symlink em ~/.grok/hooks/ sempre carrega.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SRC="${REPO_ROOT}/.grok/hooks/claude-code-import.json"
HOOK_DST="${HOME}/.grok/hooks/eddie-auto-dev-claude-code.json"

if [[ ! -f "${HOOK_SRC}" ]]; then
  echo "❌ Arquivo de hooks não encontrado: ${HOOK_SRC}" >&2
  exit 1
fi

mkdir -p "${HOME}/.grok/hooks"
ln -sfn "${HOOK_SRC}" "${HOOK_DST}"

echo "✅ Symlink criado:"
echo "   ${HOOK_DST} -> ${HOOK_SRC}"
echo ""
echo "Recarregue os hooks na sessão Grok: /hooks → r"
echo "Verifique: grok inspect | grep -A12 'Hooks'"