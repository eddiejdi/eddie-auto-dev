# WikiAgent - Referencia Completa

## Objetivo
O WikiAgent automatiza a documentacao tecnica no Wiki.js com dois modos principais:
- Publicacao de paginas novas a partir de notas brutas.
- Evolucao de paginas existentes, integrando novas informacoes no conteudo atual.

O pipeline usa Ollama local com estrategia GPU-first (GPU0, depois GPU1) e publica no Wiki.js por GraphQL.

## Localizacao no codigo
- Implementacao principal: specialized_agents/wiki_agent.py
- Registro de rotas na API: specialized_agents/api.py

## Endpoints expostos
### GET /wiki/health
Retorna status operacional do agente:
- status
- wiki_url
- ollama_gpu0 (up/down)
- ollama_gpu1 (up/down)
- default_model

### POST /wiki/publish
Publica pagina com expansao via Ollama.

Payload:
- topic: titulo da pagina.
- raw_text: notas brutas.
- wiki_path: caminho na wiki.
- tags: lista opcional de tags.
- skip_ollama: bool opcional (normalmente false neste endpoint).

Comportamento:
- Se skip_ollama=false: gera markdown estruturado via Ollama.
- Faz upsert na Wiki (create ou update).

### POST /wiki/evolve
Evolui pagina existente.

Payload:
- wiki_path: caminho existente.
- new_info: novas informacoes.
- tags: tags finais opcionais.

Comportamento:
- Busca conteudo atual via GraphQL.
- Mescla com new_info usando prompt de evolucao no Ollama.
- Atualiza pagina existente.

### POST /wiki/raw
Publica markdown sem passar no Ollama.

Payload igual ao /wiki/publish, mas o backend forca skip_ollama=true.

Uso recomendado:
- Quando o caller ja possui markdown final validado.

## Fluxo interno de execucao
### 1. Selecao de Ollama
Metodo: _pick_ollama()
- Testa GPU0 (endpoint /api/tags).
- Se indisponivel, testa GPU1.
- Se ambas indisponiveis, retorna HTTP 503.

### 2. Resolucao de modelo
Metodo: _resolve_model(base_url)
- Tenta OLLAMA_MODEL.
- Se ausente na instancia, escolhe fallback por nome preferencial (coder, qwen, llama).
- Ultimo fallback: primeiro modelo listado na instancia.

### 3. Geracao de conteudo
Metodo: _ollama_generate(system, user)
- Chama POST /api/chat com mensagens system+user.
- Parametros fixos importantes:
  - temperature=0.3
  - num_predict=8192
  - stream=false
- Erros tratados:
  - HTTP Ollama != 200 -> HTTP 502
  - Erro de conexao -> HTTP 503
  - Resposta vazia -> HTTP 502

### 4. Persistencia no Wiki.js
Metodo: _upsert_page(...)
- _get_page(path, locale)
- Se existe: _update_page(...)
- Se nao existe: _create_page(...)

## Contratos de dados (Pydantic)
### WikiPublishRequest
- topic: str (3-200)
- raw_text: str (>=10)
- wiki_path: str (3-300)
- tags: list[str] default []
- skip_ollama: bool default false

### WikiEvolveRequest
- wiki_path: str (3-300)
- new_info: str (>=10)
- tags: list[str] default []

### WikiResponse
- ok: bool
- page_id: int | None
- wiki_path: str | None
- model_used: str | None
- gpu: str | None
- message: str

## Variaveis de ambiente relevantes
- WIKI_URL: endpoint GraphQL Wiki.js.
- WIKI_TOKEN: bearer token para API.
- WIKI_LOCALE: locale da pagina (default atual no codigo: en).
- OLLAMA_MODEL: modelo principal.
- WIKI_OLLAMA_TIMEOUT: timeout de geracao.
- LLM_CONFIG.base_url: Ollama GPU0.
- LLM_GPU1_CONFIG.base_url: Ollama GPU1.

## Regras de roteamento LLM
O agente segue ordem estrita:
1. GPU0
2. GPU1

Sem fallback cloud neste modulo.

## Erros esperados e diagnostico rapido
### Nenhum Ollama disponivel
Sintoma:
- HTTP 503 com detail sobre GPU0/GPU1 offline.

Acao:
- Verificar /wiki/health.
- Verificar /api/tags nos hosts configurados.

### Falha GraphQL de permissao
Sintoma:
- HTTP 401/403/Forbidden em create/update.

Acao:
- Validar WIKI_TOKEN.
- Validar permissoes do token para create/update.
- Confirmar WIKI_URL e locale.

### Pagina nao encontrada em evolve
Sintoma:
- HTTP 404 em /wiki/evolve.

Acao:
- Confirmar wiki_path.
- Confirmar locale usado pelo agente.

## Boas praticas operacionais
- Para conteudo pronto e sensivel a formato, usar /wiki/raw.
- Para notas curtas e sem estrutura, usar /wiki/publish.
- Para manutencao incremental de pagina existente, usar /wiki/evolve.
- Monitorar /wiki/health antes de operacoes em lote.

## Exemplo de chamada /wiki/raw
```bash
curl -sS -X POST http://localhost:8503/wiki/raw \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "WikiAgent - Referencia Completa",
    "raw_text": "# Titulo\n\nConteudo markdown final.",
    "wiki_path": "homelab/agents/wiki-agent-complete-reference-2026-05-03",
    "tags": ["wiki","agent","ollama"],
    "skip_ollama": true
  }'
```

## Riscos e observacoes
- Locale padrao em codigo esta definido como en; para paginas em pt, ajustar WIKI_LOCALE no ambiente de execucao.
- O token de API deve vir de secret manager/variavel de ambiente, evitando segredo hardcoded no codigo.

## Historico
- 2026-05-03: Documento consolidado com arquitetura, contratos, fluxo de execucao, operacao e riscos do WikiAgent.
