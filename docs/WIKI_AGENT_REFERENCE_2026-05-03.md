# WikiAgent — Referência Técnica Operacional

## Objetivo
O WikiAgent centraliza publicação e evolução de documentação no Wiki.js usando Ollama local (GPU-first).

Fluxos principais:
1. Publicar: texto bruto -> expansão (opcional) via Ollama -> create/update no Wiki.js.
2. Evoluir: busca página existente -> mescla novas informações via Ollama -> update no Wiki.js.
3. Publicação direta: markdown pronto -> Wiki.js sem passar pelo Ollama.

## Localização no código
- Módulo: specialized_agents/wiki_agent.py
- Router FastAPI: endpoints sob /wiki
- Singleton: get_wiki_agent()

## Endpoints HTTP
### GET /wiki/health
Retorna saúde do agente e status das GPUs:
- status
- wiki_url
- ollama_gpu0
- ollama_gpu1
- default_model

### POST /wiki/publish
Payload:
- topic: string
- raw_text: string
- wiki_path: string
- tags: list[string]
- skip_ollama: bool

Comportamento:
- skip_ollama=false: usa _SYSTEM_EXPAND e Ollama para estruturar conteúdo.
- skip_ollama=true: publica raw_text como conteúdo final.
- Sempre faz upsert (create/update).

### POST /wiki/evolve
Payload:
- wiki_path: string
- new_info: string
- tags: list[string]

Comportamento:
- Busca página existente com singleByPath.
- Se não existir, retorna 404.
- Se existir, usa _SYSTEM_EVOLVE para integrar conteúdo novo.
- Atualiza página no Wiki.js.

### POST /wiki/raw
Atalho de publicação direta.
Internamente força skip_ollama=true e reutiliza o fluxo de publish.

## Configuração por variáveis de ambiente
- WIKI_URL (default: http://192.168.15.2:3009/graphql)
- WIKI_TOKEN (Bearer para GraphQL do Wiki.js)
- WIKI_LOCALE (default no código atual: en)
- OLLAMA_MODEL (default: shared-coder)
- WIKI_OLLAMA_TIMEOUT (default: 120)

Fontes de GPU:
- GPU0: specialized_agents.config.LLM_CONFIG.base_url
- GPU1: specialized_agents.config.LLM_GPU1_CONFIG.base_url

## Estratégia Ollama (GPU-first)
1. _pick_ollama testa /api/tags em GPU0.
2. Se GPU0 indisponível, tenta GPU1.
3. Se ambas indisponíveis, retorna HTTP 503.

Resolução de modelo:
- Prefere OLLAMA_MODEL.
- Se não existir na instância, seleciona heurística por nome (coder/qwen/llama).
- Sem match, usa primeiro modelo disponível.

Geração:
- Endpoint usado: /api/chat
- stream: false
- temperature: 0.3
- num_predict: 8192

## Integração GraphQL com Wiki.js
Métodos principais:
- _graphql(query, variables)
- _get_page(wiki_path)
- _create_page(...)
- _update_page(...)
- _upsert_page(...)

Operações:
- Busca: pages.singleByPath(path, locale)
- Criação: pages.create(...)
- Atualização: pages.update(...)

Tratamento de erros:
- HTTPError do Wiki.js é convertido em HTTPException com status original.
- Erros GraphQL em create/update geram HTTPException 502 ou 400 conforme responseResult.

## Modelos de prompt do agente
- _SYSTEM_EXPAND: transforma notas brutas em documentação técnica estruturada.
- _SYSTEM_EVOLVE: integra novas informações preservando conteúdo existente.

Regras de conteúdo impostas pelos prompts:
- Markdown completo
- Seções H2/H3
- Tabelas quando aplicável
- Blocos de código com linguagem
- Mermaid quando útil
- Seção de histórico
- Sem inventar dados técnicos

## Observabilidade
Logs principais:
- Modelo/GPU usados e tamanho da saída gerada
- Operação de wiki executada (created/updated)
- Warnings em falha de busca de página

## Testes
Cobertura do módulo em:
- tests/test_wiki_agent.py

Cenários cobertos no conjunto de testes:
- publicação raw
- evolução com página inexistente (404)
- publish com expansão via Ollama
- comportamento de endpoints

## Segurança e operação
- O token de wiki deve ser tratado como segredo operacional e rotacionável.
- Publicação deve respeitar locale correto da wiki para evitar inconsistências de URL.
- Em falhas de permissão (Forbidden), validar escopo do token API no Wiki.js.

## Exemplo de uso (publicação direta)
```bash
curl -sS -X POST http://localhost:8503/wiki/raw \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "WikiAgent — Referência Técnica",
    "raw_text": "# WikiAgent ...",
    "wiki_path": "homelab/agents/wiki-agent-reference-2026-05-03",
    "tags": ["wiki","agent","ollama","fastapi"]
  }'
```

## Exemplo de uso (evolução)
```bash
curl -sS -X POST http://localhost:8503/wiki/evolve \
  -H 'Content-Type: application/json' \
  -d '{
    "wiki_path": "homelab/agents/wiki-agent-reference-2026-05-03",
    "new_info": "Adicionar seção de troubleshooting de permissões",
    "tags": ["wiki","agent"]
  }'
```

## Troubleshooting rápido
1. HTTP 503 no publish/evolve: verificar Ollama GPU0/GPU1 no /wiki/health.
2. HTTP 502 com detalhe de Wiki.js: revisar WIKI_URL e conectividade GraphQL.
3. GraphQL Forbidden: token sem permissão de create/update.
4. Página não encontrada no evolve: validar wiki_path e locale.

## Histórico
- 2026-05-03: referência consolidada do WikiAgent criada para operação e manutenção.
