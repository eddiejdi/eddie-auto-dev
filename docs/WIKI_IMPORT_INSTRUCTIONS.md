# Instruções para Importar Página na Wiki RPA4All

**Status:** Wiki.js indisponível no momento (14/04/2026 ~14:45 UTC)

O conteúdo completo da página foi preparado e salvo localmente. Quando a conectividade com a wiki for restaurada, siga os passos abaixo:

---

## Método 1: Upload via Interface Web (Recomendado)

1. Acesse https://wiki.rpa4all.com
2. Faça login com suas credenciais Authentik
3. Clique em **"New Page"**
4. Preencha os campos:
   - **Path:** `trading/crypto-agents-restoration-2026-04-14`
   - **Title:** `Resolução - Crypto-Agents Restaurados [14/04/2026]`
   - **Description:** `Resolução do problema com crypto-agents falhando no carregamento de módulos Python de trading automático.`
   - **Editor Mode:** Markdown
   - **Tags:** `trading`, `troubleshooting`, `crypto-agents`, `infrastructure`, `2026-04-14`

5. Cole o conteúdo do arquivo: `/workspace/eddie-auto-dev/docs/WIKI_PAGE_CRYPTO_AGENTS_RESTORATION.md`
6. Clique em **"Create"**

---

## Método 2: GraphQL API (quando connectivity restaurada)

Execute este script no homelab:

```bash
#!/bin/bash

# Obter token
JWT=$(curl -s -X POST http://192.168.15.2:3009/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation{authentication{login(username:\"copilot-agent\",password:\"eddie_memory_2026\",strategy:\"local\"){responseResult{succeeded}jwt}}}"}' | grep -o '"jwt":"[^"]*' | cut -d'"' -f4)

# Ler conteúdo do arquivo
CONTENT=$(cat /workspace/eddie-auto-dev/docs/WIKI_PAGE_CRYPTO_AGENTS_RESTORATION.md)

# Criar página
curl -s -X POST http://192.168.15.2:3009/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d "{
    \"query\": \"mutation { pages { create(path: \\\"trading/crypto-agents-restoration-2026-04-14\\\", title: \\\"Resolução - Crypto-Agents Restaurados [14/04/2026]\\\", description: \\\"Resolução do problema com crypto-agents falhando no carregamento de módulos Python de trading automático.\\\", content: \\\"$CONTENT\\\", editor: \\\"markdown\\\", isPublished: true, locale: \\\"pt\\\", tags: [\\\"trading\\\", \\\"troubleshooting\\\", \\\"crypto-agents\\\", \\\"infrastructure\\\"]) { responseResult { succeeded message } page { id path } } } }\"
  }"
```

---

## Verificação Pós-Upload

Após criar a página, verifique:

1. **Acesso Público:** https://wiki.rpa4all.com/trading/crypto-agents-restoration-2026-04-14
2. **Renderização:** Todo o markdown deve aparecer corretamente
3. **Tags:** Todos os 4 tags devem estar visíveis
4. **Navegação:** A página deve aparecer em buscas por "crypto-agents" ou "troubleshooting"

---

## Detalhes Técnicos

- **Arquivo preparado:** `/workspace/eddie-auto-dev/docs/WIKI_PAGE_CRYPTO_AGENTS_RESTORATION.md`
- **Locale:** Português (pt)
- **Editor:** Markdown
- **Status de publicação:** Publicada (isPublished: true)
- **Privacidade:** Pública (isPrivate: false)

---

## Possíveis Erros

| Erro | Solução |
|------|---------|
| "API is disabled" | Usar fallback JWT login (veja Método 2) |
| "Path already exists" | Verificar se página já foi criada; usar `update` ao invés de `create` |
| "Authentication failed" | Verificar credenciais em `/memories/repo/` ou secrets |
| "GraphQL syntax error" | Validar JSON; considerar escaper caracteres especiais |

---

## Rollback

Se precisar remover/atualizar a página criada:

```bash
# Deletar página
curl -s -X POST http://192.168.15.2:3009/graphql \
  -H "Authorization: Bearer $JWT" \
  -d '{"query":"mutation { pages { delete(id: <PAGE_ID>) { responseResult { succeeded } } } }"}'

# Atualizar página existente
curl -s -X POST http://192.168.15.2:3009/graphql \
  -H "Authorization: Bearer $JWT" \
  -d '{"query":"mutation { pages { update(id: <PAGE_ID>, content: \"...\") { responseResult { succeeded } } } }"}'
```

---

**Data de Preparação:** 14/04/2026  
**Estado de Conectividade:** ⚠️ Wiki.js indisponível  
**Próximas Ações:** Retentar após restauração de conectividade
