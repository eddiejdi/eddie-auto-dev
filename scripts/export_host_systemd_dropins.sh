#!/usr/bin/env bash
# Copia para a árvore do repo os drop-ins que existem SÓ no host.
#
# Contrapartida de scripts/check_systemd_dropin_drift.py: o verificador aponta
# "host_only"; este script traz os arquivos para dentro do git, para que
# `ExecStart=`/`Environment=` vivos deixem de ser irrecuperáveis.
#
# Roda no homelab (192.168.15.2) — direto ou via runner self-hosted:
#   scripts/export_host_systemd_dropins.sh          # só lista (dry-run)
#   scripts/export_host_systemd_dropins.sh --apply  # copia para systemd/
#
# Depois: revisar segredo por segredo antes de commitar. Arquivo com credencial
# real NÃO deve ser versionado — mantenha o template com <from_bitwarden> e
# registre a exceção em docs/systemd/DROPIN_DEPLOY_PARITY.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEM_DIR="${SYSTEM_DIR:-/etc/systemd/system}"
ALLOWLIST="${REPO_ROOT}/deploy/systemd-dropins-sync.allowlist"
APPLY=0

for arg in "$@"; do
  case "${arg}" in
    --apply) APPLY=1 ;;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "❌ argumento desconhecido: ${arg}" >&2; exit 2 ;;
  esac
done

if [[ ! -f "${ALLOWLIST}" ]]; then
  echo "❌ Allowlist ausente: ${ALLOWLIST}" >&2
  exit 1
fi

# Diretorios a inspecionar = os que a allowlist toca. Escopo de OBSERVACAO:
# varre o diretorio inteiro, mesmo que so alguns arquivos sejam sincronizaveis.
observed_dirs() {
  sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "${ALLOWLIST}" \
    | grep -v '^$' | xargs -r -n1 dirname | xargs -r -n1 basename | sort -u
}

found=0
while IFS= read -r rel_dir; do
  [[ -z "${rel_dir}" ]] && continue

  host_dir="${SYSTEM_DIR}/${rel_dir}"
  repo_dir="${REPO_ROOT}/systemd/${rel_dir}"
  [[ -d "${host_dir}" ]] || continue

  for host_file in "${host_dir}"/*.conf; do
    [[ -f "${host_file}" ]] || continue
    base="$(basename "${host_file}")"
    [[ -f "${repo_dir}/${base}" ]] && continue

    found=$((found + 1))
    echo "⚠️  host-only: ${rel_dir}/${base}"
    if [[ "${APPLY}" -eq 1 ]]; then
      mkdir -p "${repo_dir}"
      sudo cat "${host_file}" > "${repo_dir}/${base}"
      chmod 0644 "${repo_dir}/${base}"
      echo "    ↳ copiado para systemd/${rel_dir}/${base}"
    fi
  done
done < <(observed_dirs)

if [[ "${found}" -eq 0 ]]; then
  echo "✅ Nenhum drop-in exclusivo do host nos diretórios gerenciados."
  exit 0
fi

if [[ "${APPLY}" -eq 0 ]]; then
  echo ""
  echo "ℹ️  Dry-run: ${found} arquivo(s). Rode com --apply para copiá-los ao repo."
else
  echo ""
  echo "✅ ${found} arquivo(s) copiado(s). REVISE segredos antes de 'git add'."
fi
