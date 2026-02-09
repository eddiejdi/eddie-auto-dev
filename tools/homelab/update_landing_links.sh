#!/usr/bin/env bash
set -euo pipefail

# Atualiza os links de Jira e Confluence no landing page em /var/www/rpa4all.com/index.html
# Faz backup antes e tenta recarregar o nginx no final.

FILE=/var/www/rpa4all.com/index.html
TIMESTAMP=$(date +%Y%m%d%H%M%S)
BACKUP=${FILE}.bak_${TIMESTAMP}

if [ ! -f "$FILE" ]; then
  echo "Arquivo $FILE não encontrado" >&2
  exit 2
fi

echo "Fazendo backup em $BACKUP"
cp -- "$FILE" "$BACKUP"

# URLs Atlassian Cloud
JIRA_URL="https://rpa4all.atlassian.net"
CONFLUENCE_URL="https://rpa4all.atlassian.net/wiki"

# If existing Jira/Confluence links, replace them; otherwise insert before Contato button
if grep -q "jira.rpa4all.com\|confluence.rpa4all.com\|rpa4all.atlassian.net" "$FILE"; then
  echo "Substituindo links existentes por URLs Atlassian Cloud"
  sed -i -E "s#https?://[^\"[:space:]]*jira[^\"[:space:]]*#${JIRA_URL}#g" "$FILE" || true
  sed -i -E "s#https?://[^\"[:space:]]*confluence[^\"[:space:]]*#${CONFLUENCE_URL}#g" "$FILE" || true
else
  echo "Inserindo links Jira e Confluence no menu (antes do botão Contato)"
  awk -v j="$JIRA_URL" -v c="$CONFLUENCE_URL" '{
    if ($0 ~ /<button class="tab" data-target="contact">Contato<\/button>/) {
      print "<a class=\"tab\" href=\"" j "\">Jira<\/a>";
      print "<a class=\"tab\" href=\"" c "\">Confluence<\/a>";
    }
    print
  }' "$FILE" > "${FILE}.tmp" && mv "${FILE}.tmp" "$FILE"
fi

echo "Atualização aplicada. Testando configuração do nginx..."
if nginx -t &>/dev/null; then
  echo "nginx config OK — recarregando nginx"
  sudo systemctl reload nginx || sudo nginx -s reload
  echo "nginx recarregado"
else
  echo "Falha no teste de configuração do nginx (nginx -t falhou). Verifique permissões de certificados." >&2
  exit 3
fi

echo "Pronto. Backup salvo em: $BACKUP"
#!/usr/bin/env bash
set -euo pipefail

# Atualiza os links de Jira e Confluence no landing page em /var/www/rpa4all.com/index.html
# Faz backup antes e tenta recarregar o nginx no final.

FILE=/var/www/rpa4all.com/index.html
TIMESTAMP=$(date +%Y%m%d%H%M%S)
BACKUP=${FILE}.bak_${TIMESTAMP}

if [ ! -f "$FILE" ]; then
  echo "Arquivo $FILE não encontrado" >&2
  exit 2
fi

echo "Fazendo backup em $BACKUP"
cp -- "$FILE" "$BACKUP"

# URLs Atlassian Cloud
JIRA_URL="https://rpa4all.atlassian.net"
CONFLUENCE_URL="https://rpa4all.atlassian.net/wiki"

# If existing Jira/Confluence links, replace them; otherwise insert before Contato button
if grep -q "jira.rpa4all.com\|confluence.rpa4all.com\|rpa4all.atlassian.net" "$FILE"; then
  echo "Substituindo links existentes por URLs Atlassian Cloud"
  sed -i -E "s#https?://[^\"[:space:]]*jira[^\"[:space:]]*#${JIRA_URL}#g" "$FILE" || true
  sed -i -E "s#https?://[^\"[:space:]]*confluence[^\"[:space:]]*#${CONFLUENCE_URL}#g" "$FILE" || true
else
  echo "Inserindo links Jira e Confluence no menu (antes do botão Contato)"
  awk -v j="$JIRA_URL" -v c="$CONFLUENCE_URL" '{
    if ($0 ~ /<button class="tab" data-target="contact">Contato<\/button>/) {
      print "<a class=\"tab\" href=\"" j "\">Jira<\/a>";
      print "<a class=\"tab\" href=\"" c "\">Confluence<\/a>";
    }
    print
  }' "$FILE" > "${FILE}.tmp" && mv "${FILE}.tmp" "$FILE"
fi

echo "Atualização aplicada. Testando configuração do nginx..."
if nginx -t &>/dev/null; then
  echo "nginx config OK — recarregando nginx"
  sudo systemctl reload nginx || sudo nginx -s reload
  echo "nginx recarregado"
else
  echo "Falha no teste de configuração do nginx (nginx -t falhou). Verifique permissões de certificados." >&2
  exit 3
fi

echo "Pronto. Backup salvo em: $BACKUP"
#!/usr/bin/env bash
set -euo pipefail

# Atualiza os links de Jira e Confluence no landing page em /var/www/rpa4all.com/index.html
# Faz backup antes e tenta recarregar o nginx no final.

FILE=/var/www/rpa4all.com/index.html
TIMESTAMP=$(date +%Y%m%d%H%M%S)
BACKUP=${FILE}.bak_${TIMESTAMP}

if [ ! -f "$FILE" ]; then
  echo "Arquivo $FILE não encontrado" >&2
  exit 2
fi

echo "Fazendo backup em $BACKUP"
cp -- "$FILE" "$BACKUP"

# URLs Atlassian Cloud
JIRA_URL="https://rpa4all.atlassian.net"
CONFLUENCE_URL="https://rpa4all.atlassian.net/wiki"

# If existing Jira/Confluence links, replace them; otherwise insert before Contato button
if grep -q "jira.rpa4all.com\|confluence.rpa4all.com\|rpa4all.atlassian.net" "$FILE"; then
  echo "Substituindo links existentes por URLs Atlassian Cloud"
  sed -i -E "s#https?://[^"]*(jira|confluence)[^"]*#${JIRA_URL}#g" "$FILE" || true
  sed -i -E "s#https?://[^"]*confluence[^"]*#${CONFLUENCE_URL}#g" "$FILE" || true
else
  echo "Inserindo links Jira e Confluence no menu (antes do botão Contato)"
  sed -i "/<button class=\"tab\" data-target=\"contact\">Contato<\/button>/i \
<a class=\"tab\" href=\"${JIRA_URL}\">Jira<\/a>\n<a class=\"tab\" href=\"${CONFLUENCE_URL}\">Confluence<\/a>" "$FILE"
fi

echo "Atualização aplicada. Testando configuração do nginx..."
if nginx -t &>/dev/null; then
  echo "nginx config OK — recarregando nginx"
  sudo systemctl reload nginx || sudo nginx -s reload
  echo "nginx recarregado"
else
  echo "Falha no teste de configuração do nginx (nginx -t falhou). Verifique permissões de certificados." >&2
  exit 3
fi

echo "Pronto. Backup salvo em: $BACKUP"
