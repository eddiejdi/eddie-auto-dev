# Upload Manual de Documentação → Wiki.js

## 1. Acessar Wiki.js

```
http://192.168.15.2:3009
```

**Autenticação**: 
- Via Authentik OIDC (recomendado)
- Fallback: Local auth (admin@rpa4all.com / credencial em Bitwarden)

---

## 2. Criar Páginas

### Página 1: Status Operacional

**Caminho na Wiki**: `System Operations / Operational Status 2026-04-13`

**Conteúdo**: Copiar de `/workspace/eddie-auto-dev/docs/OPERATIONAL_STATUS_2026-04-13.md`

**Metadados**:
- Título: "Status Operacional — 13 de abril de 2026"
- Descrição: "Snapshot de todos os sistemas operacionais: VPN Panamá, Wiki.js OIDC, iVentoy, infraestrutura"
- Tags: `operational`, `vpn`, `wiki`, `oidc`, `infrastructure`

### Página 2: Lições Aprendidas

**Caminho na Wiki**: `Knowledge Base / Lessons Learned 2026-04-13`

**Conteúdo**: Copiar de `/workspace/eddie-auto-dev/docs/LESSONS_LEARNED_2026-04-13.md`

**Metadados**:
- Título: "Lições Aprendidas — VPN, OIDC, Containers (13 de abril 2026)"
- Descrição: "13 lições técnicas sobre decisões e padrões de implementação"
- Tags: `lessons`, `vpn`, `oidc`, `containers`, `infrastructure`, `deployment`

---

## 3. Passos Detalhados (Interface Web)

### Via UI Web

1. **Login**: Clicar "Sign in" → Authentik SSO
2. **Nova Página**: Clicar "+" / "Create Page"
3. **Preencher**:
   - Title: (conforme acima)
   - Path: (inferido automaticamente ou manual)
   - Set as Published: ✅
   - Language: Português (Brasil)
4. **Editor**: Paste do conteúdo Markdown
5. **Salvar**: Clicar "Create" → confirmar

### Alternativa: Via GraphQL (curl)

```bash
WIKI_URL="http://192.168.15.2:3009"
WIKI_TOKEN="<api-key-from-bitwarden>"

curl -X POST "${WIKI_URL}/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${WIKI_TOKEN}" \
  -d '{
    "query": "mutation CreatePage($input: PageCreateInput!) { pages { create(input: $input) { id path } } }",
    "variables": {
      "input": {
        "title": "Status Operacional — 2026-04-13",
        "path": "system-operations/status-2026-04-13",
        "content": "<conteudo-markdown>",
        "isPublished": true,
        "locale": "pt-BR"
      }
    }
  }'
```

---

## 4. Arquivos Fonte

Todos os arquivos estão versionados em Git:

```
/workspace/eddie-auto-dev/
├── docs/
│   ├── OPERATIONAL_STATUS_2026-04-13.md
│   ├── LESSONS_LEARNED_2026-04-13.md
│   └── VPN_PANAMA_CONFIG_2026-04-12.md
└── tools/
    └── publish_docs_to_wiki.py  (script automático, futuro)
```

---

## 5. Validação

Após publicar, verificar:

- [ ] Páginas aparecem em busca: `search → "operacional"`
- [ ] Links internos funcionam
- [ ] Tabelas renderizadas corretamente
- [ ] Links externos (GitHub) acessíveis

---

## 6. Rollback

Se necessário remover:

1. **Via UI**: Página → Menu → Delete
2. **Via GraphQL**: `pages { delete(id: "page-id") }`

---

**Referência**: 
- Wiki.js docs: https://docs.requarks.io/
- Authentik OIDC: http://192.168.15.2:9000

