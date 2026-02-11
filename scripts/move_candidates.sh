#!/usr/bin/env bash
set -euo pipefail

# move_candidates.sh
# Safe helper to identify and move large, non-critical files from /home/homelab to /mnt/storage/parked
# Usage (dry-run default): sudo ./scripts/move_candidates.sh --dry-run
# To execute: sudo ./scripts/move_candidates.sh --execute

DEST=/mnt/storage/parked
DAYS=30
DRY_RUN=1
VERBOSE=1
LOG_FILE=/tmp/move_candidates_$(date +%Y%m%d_%H%M%S).log
CANDIDATES_FILE=/tmp/move_candidates_list.txt

usage(){
  cat <<EOF
Usage: $0 [--dry-run] [--execute] [--days N] [--dest PATH]

Options:
  --dry-run     (default) only list candidates and total size
  --execute     actually move candidates (uses rsync then removes source if successful)
  --days N      select files/dirs not modified in the last N days (default ${DAYS})
  --dest PATH   destination directory (default ${DEST})

Important:
  - Run this script as root (sudo) on the homelab host.
  - Review the candidate list before executing.
  - This script avoids obvious service dirs (mysql, docker, /var/lib) and skips dotfiles.
EOF
}

# parse args
while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift;;
    --execute) DRY_RUN=0; shift;;
    --days) DAYS="$2"; shift 2;;
    --dest) DEST="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ $(id -u) -ne 0 ]]; then
  echo "ERROR: run with sudo/root"
  exit 2
fi

mkdir -p "$DEST"

echo "Log: $LOG_FILE"
: > "$LOG_FILE"

# Build candidate list safely.
# Rules (conservative):
# - files with common large extensions older than $DAYS days
# - directories named Downloads, archives, backups older than $DAYS days
# - skip paths containing: "/var/", "/etc/", "/proc/", "/sys/", "/run/", "docker", "mysql", "mariadb", "/home/homelab/.ssh"

echo "Gerando lista de candidatos (dias > $DAYS) ..." | tee -a "$LOG_FILE"

# find large files by extension
find /home/homelab -type f \( -iname '*.iso' -o -iname '*.img' -o -iname '*.vdi' -o -iname '*.qcow2' -o -iname '*.tar.gz' -o -iname '*.zip' \) -mtime +${DAYS} \
  -not -path '*/.ssh/*' -not -path '*/.cache/*' -print > "$CANDIDATES_FILE" || true

# find likely-large dirs by name and age (only top-level under homelab)
find /home/homelab -maxdepth 2 -type d \( -iname 'Downloads' -o -iname 'archives' -o -iname 'backup*' -o -iname 'backups' \) -mtime +${DAYS} -print >> "$CANDIDATES_FILE" || true

# include model/ollama caches if present and old
find /home/homelab -type d -iname '*ollama*' -mtime +${DAYS} -print >> "$CANDIDATES_FILE" 2>/dev/null || true
find /home/homelab -type d -iname '*models*' -mtime +${DAYS} -print >> "$CANDIDATES_FILE" 2>/dev/null || true

# dedupe
sort -u "$CANDIDATES_FILE" -o "$CANDIDATES_FILE"

if [[ ! -s "$CANDIDATES_FILE" ]]; then
  echo "Nenhum candidato encontrado. Ajuste --days ou analise manualmente." | tee -a "$LOG_FILE"
  exit 0
fi

# show candidates with sizes
echo "Candidatos (caminho e tamanho):" | tee -a "$LOG_FILE"
while IFS= read -r p; do
  du -sh "$p" 2>/dev/null | tee -a "$LOG_FILE"
done < "$CANDIDATES_FILE"

TOTAL_BYTES=$(du -cb $(<"$CANDIDATES_FILE") 2>/dev/null | tail -n1 | awk '{print $1}') || TOTAL_BYTES=0
TOTAL_HUMAN=$(numfmt --to=iec-i --suffix=B $TOTAL_BYTES 2>/dev/null || echo "~")

echo "Total estimado a mover: $TOTAL_HUMAN" | tee -a "$LOG_FILE"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "--- DRY RUN ---\nRevise $CANDIDATES_FILE e o log $LOG_FILE. Para executar: sudo $0 --execute" | tee -a "$LOG_FILE"
  exit 0
fi

# Execution path: rsync each candidate and remove original on success
echo "Iniciando movimentação para $DEST" | tee -a "$LOG_FILE"

for path in $(cat "$CANDIDATES_FILE"); do
  if [[ -e "$path" ]]; then
    base=$(basename "$path")
    dst="$DEST/$(hostname)-${base}"
    echo "Movendo $path -> $dst" | tee -a "$LOG_FILE"
    mkdir -p "$dst"
    # if it's a directory, rsync -a; if file, rsync file
    if [[ -d "$path" ]]; then
      rsync -aHAX --info=progress2 --delete --partial --progress "$path/" "$dst/" | tee -a "$LOG_FILE"
      # verify sizes
      src_sz=$(du -sb "$path" | cut -f1)
      dst_sz=$(du -sb "$dst" | cut -f1)
      if [[ "$src_sz" -eq "$dst_sz" ]]; then
        rm -rf "$path"
        echo "Removido origem: $path" | tee -a "$LOG_FILE"
      else
        echo "AVISO: tamanhos divergentes para $path (src=$src_sz dst=$dst_sz). Não removido." | tee -a "$LOG_FILE"
      fi
    else
      # file
      rsync -a --progress "$path" "$dst/" | tee -a "$LOG_FILE"
      src_sz=$(stat -c%s "$path")
      dst_file="$dst/$(basename "$path")"
      dst_sz=$(stat -c%s "$dst_file" 2>/dev/null || echo 0)
      if [[ "$src_sz" -eq "$dst_sz" ]]; then
        rm -f "$path"
        echo "Removido arquivo origem: $path" | tee -a "$LOG_FILE"
      else
        echo "AVISO: arquivo size mismatch $path (src=$src_sz dst=$dst_sz)." | tee -a "$LOG_FILE"
      fi
    fi
  else
    echo "Ignorado (não existe): $path" | tee -a "$LOG_FILE"
  fi
done

# cleanup empty parent dirs (conservative)
while IFS= read -r p; do
  parent=$(dirname "$p")
  if [[ -d "$parent" && -z "$(ls -A "$parent")" ]]; then
    rmdir "$parent" && echo "Removed empty parent: $parent" | tee -a "$LOG_FILE" || true
  fi
done < "$CANDIDATES_FILE"

echo "Movimentação concluída. Verifique uso de disco: df -h $DEST" | tee -a "$LOG_FILE"
exit 0
