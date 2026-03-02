#!/usr/bin/env bash
# tools/check_btc_agent.sh
# Uso: DB_PASS=... ./tools/check_btc_agent.sh
set -euo pipefail
SSH_USER="${SSH_USER:-homelab}"
SSH_HOST="${SSH_HOST:-192.168.15.2}"
API_PORTS=(8511 8510 8512)
ENDPOINTS=("/health" "/trades/last" "/trades?limit=1" "/api/trades/last" "/v1/trades/last")
TIMEOUT="${TIMEOUT:-30}"
RAW_OUT="/tmp/btc_agent_check.raw"
JSON_OUT="/tmp/btc_agent_check.json"
LOGS_TMP="/tmp/btc_agent_logs.tmp"
> "$RAW_OUT"
echo "START_TIME: $(date --iso-8601=seconds)" >> "$RAW_OUT"

# Helper: run curl with timeout and return body + http code on separate last line
curl_probe() {
  local url="$1"
  # Return body then newline then http code
  curl -sS -m "$TIMEOUT" -H "Accept: application/json" -w "\n%{http_code}" "$url" 2>&1 || true
}

# 1) Validate SSH (batch mode): try key-based first
echo "== SSH CONNECTION TEST ==" | tee -a "$RAW_OUT"
SSH_OK="no"
if ssh -o BatchMode=yes -o ConnectTimeout=10 "${SSH_USER}@${SSH_HOST}" 'echo SSH_OK' >/tmp/_ssh_test.out 2>&1; then
  SSH_OK="yes"
  echo "SSH key auth: OK" | tee -a "$RAW_OUT"
else
  echo "SSH key auth: FAILED (will attempt normal SSH, may prompt for password)" | tee -a "$RAW_OUT"
  # Try interactive connection check (may ask for password)
  if ssh -o ConnectTimeout=10 "${SSH_USER}@${SSH_HOST}" 'echo SSH_OK' >/tmp/_ssh_test.out 2>&1; then
    SSH_OK="yes"
    echo "SSH interactive: OK" | tee -a "$RAW_OUT"
  else
    SSH_OK="no"
    echo "SSH failed completely. Aborting remote fallback steps." | tee -a "$RAW_OUT"
  fi
fi
echo "SSH_OK=$SSH_OK" >> "$RAW_OUT"
echo "" >> "$RAW_OUT"

# 2) Try API endpoints (prioridade: ports then endpoints)
echo "== API PROBES ==" | tee -a "$RAW_OUT"
service_status="no_response"
last_trade_json=""
api_raw_resp=""
api_http_code=""
found_api_port=""
found_api_path=""
for port in "${API_PORTS[@]}"; do
  for path in "${ENDPOINTS[@]}"; do
    url="http://${SSH_HOST}:${port}${path}"
    echo "Probing $url" | tee -a "$RAW_OUT"
    resp="$(curl_probe "$url")"
    # separate last line as http code
    http_code="$(printf '%s' "$resp" | tail -n1)"
    body="$(printf '%s' "$resp" | sed '$d')"
    echo "HTTP_CODE=$http_code" >> "$RAW_OUT"
    echo "BODY_PREVIEW: $(printf '%.400s' "$body")" >> "$RAW_OUT"
    if [[ "$http_code" =~ ^2|^3 ]]; then
      service_status="HTTP ${http_code}"
      api_raw_resp="$body"
      api_http_code="$http_code"
      found_api_port="$port"
      found_api_path="$path"
      # If this endpoint looks like trades, try to extract last trade JSON
      if printf '%s\n' "$body" | jq -e . >/dev/null 2>&1; then
        # Try several heuristics to find a trade object
        last_trade_json="$(printf '%s' "$body" | jq 'if type=="array" then .[0] elif .trade then .trade elif .data and (.data|type=="array") then .data[0] else . end')"
      else
        last_trade_json=""
      fi
      break 2
    fi
    # else continue
  done
done

if [ "$service_status" = "no_response" ]; then
  echo "API não respondeu em nenhum endpoint/porta testado." | tee -a "$RAW_OUT"
else
  echo "API respondeu em http://${SSH_HOST}:${found_api_port}${found_api_path} -> $service_status" | tee -a "$RAW_OUT"
fi
echo "" >> "$RAW_OUT"

# 3) Fallback: DB query via SSH if API didn't return a trade
db_fallback_output=""
used_db_fallback="no"
if [ -z "${last_trade_json:-}" ] || [ "$last_trade_json" = "null" ]; then
  echo "== DB FALLBACK (via SSH) ==" | tee -a "$RAW_OUT"
  if [ "$SSH_OK" = "yes" ]; then
    used_db_fallback="yes"
    # Prefer DB_PASS environment variable; do NOT print it.
    DB_PASS_VAR="${DB_PASS:-}"
    # Build psql command to return row as JSON
    PSQL_CMD="SET search_path TO btc, public; SELECT row_to_json(t) FROM (SELECT * FROM trades ORDER BY executed_at DESC LIMIT 1) t;"
    if [ -n "$DB_PASS_VAR" ]; then
      # Use PGPASSWORD in-line (won't be printed)
      ssh "${SSH_USER}@${SSH_HOST}" "PGPASSWORD='${DB_PASS_VAR}' psql -At -F '' -c \"${PSQL_CMD}\"" > /tmp/_psql_out 2>/tmp/_psql_err || true
      cat /tmp/_psql_err >> "$RAW_OUT" 2>/dev/null || true
      db_fallback_output="$(cat /tmp/_psql_out || true)"
    else
      # Try without PGPASSWORD (may prompt)
      ssh "${SSH_USER}@${SSH_HOST}" "psql -At -F '' -c \"${PSQL_CMD}\"" > /tmp/_psql_out 2>/tmp/_psql_err || true
      cat /tmp/_psql_err >> "$RAW_OUT" 2>/dev/null || true
      db_fallback_output="$(cat /tmp/_psql_out || true)"
    fi
    echo "DB RAW: $(printf '%.400s' "$db_fallback_output")" >> "$RAW_OUT"
    # If DB output looks like JSON, set last_trade_json
    if printf '%s' "$db_fallback_output" | jq -e . >/dev/null 2>&1; then
      last_trade_json="$(printf '%s' "$db_fallback_output" | jq '.')"
    fi
  else
    echo "SSH não disponível; não foi possível consultar o banco como fallback." | tee -a "$RAW_OUT"
  fi
fi
echo "" >> "$RAW_OUT"

# 4) Docker container + logs (via SSH)
echo "== DOCKER CONTAINERS (btc) ==" | tee -a "$RAW_OUT"
container_name=""
container_status=""
container_image=""
if [ "$SSH_OK" = "yes" ]; then
  ssh "${SSH_USER}@${SSH_HOST}" "docker ps --filter name=btc -a --format '{{.Names}}\t{{.Status}}\t{{.Image}}'" > /tmp/_docker_ps 2>/tmp/_docker_ps_err || true
  cat /tmp/_docker_ps_err >> "$RAW_OUT" 2>/dev/null || true
  docker_ps_out="$(cat /tmp/_docker_ps || true)"
  echo "$docker_ps_out" >> "$RAW_OUT"
  # pick first matching line if any
  if [ -n "$docker_ps_out" ]; then
    # take first non-empty line
    line="$(printf '%s\n' "$docker_ps_out" | sed -n '1p' )"
    container_name="$(printf '%s' "$line" | awk -F'\t' '{print $1}')"
    container_status="$(printf '%s' "$line" | awk -F'\t' '{print $2}')"
    container_image="$(printf '%s' "$line" | awk -F'\t' '{print $3}')"
    # fetch logs tail 200
    echo "Fetching logs for container '$container_name' (tail 200)..." >> "$RAW_OUT"
    ssh "${SSH_USER}@${SSH_HOST}" "docker logs --tail 200 ${container_name} 2>&1" > "$LOGS_TMP" || true
  fi
else
  echo "SSH not available; skipping docker checks." >> "$RAW_OUT"
fi

# Prepare logs_tail: up to 200 lines raw, but we will keep upto 30 lines for JSON output (concise)
logs_tail_full=""
logs_tail_30=""
if [ -f "$LOGS_TMP" ]; then
  logs_tail_full="$(tail -n 200 "$LOGS_TMP" || true)"
  # select last 30 non-empty lines concisely
  logs_tail_30="$(printf '%s\n' "$logs_tail_full" | tail -n 200 | sed -n '/./,$p' | tail -n 30)"
fi

# 5) Build final JSON result
summary_status="DOWN"
# Determine summary: OK if API responded and last_trade exists; DEGRADED if only DB fallback found or container down; else DOWN
if [ -n "${last_trade_json:-}" ] && [ "${last_trade_json}" != "null" ]; then
  if [ "$service_status" != "no_response" ]; then
    summary_status="OK"
  else
    summary_status="DEGRADED"
  fi
else
  summary_status="DOWN"
fi

# Prepare fields for JSON safely (escaping)
jq -n --arg summary "$summary_status" \
  --arg service_status "${service_status:-no_response}" \
  --argjson last_trade "$(printf '%s' "${last_trade_json:-null}" | jq -c '.' 2>/dev/null || echo 'null')" \
  --arg db_fallback "$(printf '%.200s' "${db_fallback_output:-""}" )" \
  --arg container "$( [ -n "$container_name" ] && printf '%s (%s) image=%s' "$container_name" "$container_status" "$container_image" || echo 'null' )" \
  --arg logs_tail "$(printf '%s' "$logs_tail_30")" \
  --arg ssh_ok "$SSH_OK" \
  --arg api_probe "host:${SSH_HOST} ports:${API_PORTS[*]} path:${found_api_path:-}" \
  '{
    summary: $summary,
    service_status: $service_status,
    last_trade: $last_trade,
    db_fallback: ($db_fallback|if .=="" then null else . end),
    container: ($container|if .=="null" then null else . end),
    logs_tail: ($logs_tail|if .=="" then null else . end),
    errors: [],
    meta: { ssh_ok: $ssh_ok, api_probe: $api_probe }
  }' > "$JSON_OUT"

# Print raw outputs and final JSON
echo "===== RAW OUTPUTS (arquivo: $RAW_OUT) ====="
cat "$RAW_OUT" || true
echo ""
if [ -f /tmp/_psql_out ]; then
  echo "===== DB RAW OUTPUT (/tmp/_psql_out) ====="
  sed -n '1,200p' /tmp/_psql_out || true
  echo ""
fi
if [ -f /tmp/_docker_ps ]; then
  echo "===== DOCKER PS OUTPUT (/tmp/_docker_ps) ====="
  sed -n '1,200p' /tmp/_docker_ps || true
  echo ""
fi
if [ -f "$LOGS_TMP" ]; then
  echo "===== CONTAINER LOGS (last 200 lines) ====="
  sed -n '1,200p' "$LOGS_TMP" || true
  echo ""
fi

echo "===== SUMMARY JSON ====="
cat "$JSON_OUT"
echo ""
echo "===== RESUMO (PT-BR) ====="
# Build concise PT-BR summary
jq -r '
  . as $all |
  "summary: \($all.summary)\nservice_status: \($all.service_status)\nlast_trade: \($all.last_trade // "null")\ndb_fallback: \($all.db_fallback // "null")\ncontainer: \($all.container // "null")\nlogs_tail: \($all.logs_tail // "null")\nerrors: \($all.errors | join("; "))"
' "$JSON_OUT"

