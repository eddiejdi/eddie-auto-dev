#!/usr/bin/env bash
# Instala os hooks do eddie-auto-dev no opencode via symlink global.
# O opencode auto-carrega todo arquivo em ~/.config/opencode/plugins/.
# O plugin aplica os hooks Python (tools/copilot_hooks + tools/hooks) em
# qualquer sessão; repo-root é descoberto com fallback /workspace/eddie-auto-dev.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_SRC="${REPO_ROOT}/.opencode/plugins/rpa4all-hooks.ts"
PLUGIN_DST="${HOME}/.config/opencode/plugins/rpa4all-hooks.ts"

if [[ ! -f "${PLUGIN_SRC}" ]]; then
  echo "❌ Plugin não encontrado: ${PLUGIN_SRC}" >&2
  exit 1
fi

mkdir -p "${HOME}/.config/opencode/plugins"
ln -sfn "${PLUGIN_SRC}" "${PLUGIN_DST}"

echo "✅ Symlink criado:"
echo "   ${PLUGIN_DST} -> ${PLUGIN_SRC}"
echo ""
echo "Reinicie o opencode para carregar o plugin."
echo "Verifique: opencode (settins) → Plugins, ou teste com um comando destrutivo"
echo "ex.: 'rm -rf' deve ser bloqueado pelo pre_tool_guardrails.py."