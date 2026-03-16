#!/bin/bash

set -euo pipefail

GRAFANA_HOST="${GRAFANA_HOST:-127.0.0.1}"
GRAFANA_PORT="${GRAFANA_PORT:-3002}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus:9090}"

BASE_URL="http://${GRAFANA_HOST}:${GRAFANA_PORT}"
AUTH="${GRAFANA_USER}:${GRAFANA_PASSWORD}"
DASHBOARD_FILE="$(cd "$(dirname "$0")/../../grafana/dashboards" && pwd)/conube-operational.json"

echo "Grafana: ${BASE_URL}"
echo "Prometheus datasource target: ${PROMETHEUS_URL}"

curl -fsS "${BASE_URL}/api/health" >/dev/null

curl -fsS -u "${AUTH}" "${BASE_URL}/api/datasources/uid/dfc0w4yioe4u8e" >/dev/null 2>&1 || \
curl -fsS -X POST "${BASE_URL}/api/datasources" \
  -H "Content-Type: application/json" \
  -u "${AUTH}" \
  --data-raw "{
    \"name\": \"Prometheus\",
    \"uid\": \"dfc0w4yioe4u8e\",
    \"type\": \"prometheus\",
    \"url\": \"${PROMETHEUS_URL}\",
    \"access\": \"proxy\",
    \"isDefault\": true,
    \"jsonData\": {\"timeInterval\": \"15s\"}
  }" >/dev/null

curl -fsS -X POST "${BASE_URL}/api/dashboards/db" \
  -H "Content-Type: application/json" \
  -u "${AUTH}" \
  --data @- <<EOF >/dev/null
{
  "dashboard": $(cat "${DASHBOARD_FILE}"),
  "overwrite": true
}
EOF

echo "Dashboard Conube importado em ${BASE_URL}"
