#!/bin/bash
set -e

POSTGRES_HOST="localhost"
POSTGRES_PORT="5433"
POSTGRES_USER="eddie"
MAX_ATTEMPTS=30
ATTEMPT=0

echo "⏳ Aguardando Postgres em ${POSTGRES_HOST}:${POSTGRES_PORT}..."

while [ ${ATTEMPT} -lt ${MAX_ATTEMPTS} ]; do
    if pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -q 2>/dev/null; then
        echo "✅ Postgres está pronto!"
        exit 0
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "  Tentativa ${ATTEMPT}/${MAX_ATTEMPTS}..."
    sleep 1
done

echo "❌ Postgres não respondeu após ${MAX_ATTEMPTS} segundos"
exit 1
