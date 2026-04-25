#!/usr/bin/env bash
# Gera dump e export LTFS rotativo (para agendamento cron/systemd timer).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR" && pwd)"

LOG_DIR="/var/log"
if [ ! -d "$LOG_DIR" ] || [ ! -w "$LOG_DIR" ]; then
	LOG_DIR="/tmp"
fi
LOG_FILE="$LOG_DIR/ltfs_backup_catalog.log"
ERR_FILE="$LOG_DIR/ltfs_export.err"

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

echo "$(timestamp) - starting ltfs backup" >> "$LOG_FILE"

# Detecta disponibilidade e subcomandos do ltfs-catalog para diagnostico
if command -v ltfs-catalog >/dev/null 2>&1; then
	LTFS_HELP=$(ltfs-catalog --help 2>&1 || true)
	echo "$(timestamp) - ltfs-catalog --help output:\n${LTFS_HELP}" >> "$LOG_FILE"
	if echo "$LTFS_HELP" | grep -q -E '\bexport\b'; then
		echo "$(timestamp) - ltfs-catalog supports 'export' subcommand" >> "$LOG_FILE"
	else
		echo "$(timestamp) - NOTICE: ltfs-catalog does NOT support 'export'; fallback to 'list' will be used" >> "$ERR_FILE"
	fi
else
	echo "$(timestamp) - ERROR: ltfs-catalog not found in PATH" >> "$ERR_FILE"
fi

# Executa o utilitário Python e captura saída/erros para logs
PY_OUT=$(mktemp)
PY_ERR=$(mktemp)
RC=0

# Localiza o script ltfs_recovery.py. Pode ser sobrescrito pela variável
# de ambiente `LTFS_RECOVERY_PY` (útil quando o wrapper vive em /usr/local/bin).
if [ -n "${LTFS_RECOVERY_PY:-}" ]; then
	RECOVERY_PY="$LTFS_RECOVERY_PY"
else
	RECOVERY_PY=""
	candidates=(
		"$ROOT_DIR/ltfs_recovery.py"
		"$ROOT_DIR/../tools/ltfs_recovery.py"
		"/usr/local/tools/ltfs_recovery.py"
		"/usr/local/bin/ltfs_recovery.py"
		"/usr/local/lib/ltfs_recovery.py"
	)
	for c in "${candidates[@]}"; do
		if [ -f "$c" ]; then
			RECOVERY_PY="$c"
			break
		fi
	done
fi

if [ -z "$RECOVERY_PY" ]; then
	echo "$(timestamp) - ERROR: ltfs_recovery.py not found; set LTFS_RECOVERY_PY to override" >> "$ERR_FILE"
	rm -f "$PY_OUT" "$PY_ERR"
	exit 2
fi

echo "$(timestamp) - using ltfs_recovery.py: $RECOVERY_PY" >> "$LOG_FILE"

if ! python3 "$RECOVERY_PY" --backup-catalog >"$PY_OUT" 2>"$PY_ERR"; then
	RC=$?
fi

echo "$(timestamp) - ltfs_recovery.py exit code: $RC" >> "$LOG_FILE"
if [ -s "$PY_OUT" ]; then
	echo "$(timestamp) - STDOUT (first 200 lines):" >> "$LOG_FILE"
	sed -n '1,200p' "$PY_OUT" >> "$LOG_FILE"
fi
if [ -s "$PY_ERR" ]; then
	echo "$(timestamp) - STDERR (first 200 lines):" >> "$ERR_FILE"
	sed -n '1,200p' "$PY_ERR" >> "$ERR_FILE"
fi

rm -f "$PY_OUT" "$PY_ERR"

if [ "$RC" -ne 0 ]; then
	echo "$(timestamp) - Backup failed with exit code $RC" >> "$ERR_FILE"
	exit "$RC"
fi

echo "$(timestamp) - backup completed successfully" >> "$LOG_FILE"
exit 0
