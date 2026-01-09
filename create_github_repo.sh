#!/bin/bash
# Script para criar repositório GitHub

GITHUB_TOKEN="${GITHUB_TOKEN:-}"
REPO_NAME="eddie-auto-dev"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Erro: GITHUB_TOKEN não definido"
    exit 1
fi

curl -s -X POST "https://api.github.com/user/repos" \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"'$REPO_NAME'","private":false,"description":"Auto-Desenvolvimento com Deploy CI/CD"}'
