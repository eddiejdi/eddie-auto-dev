# Plano de Reorganização e Refatoração - Shared Auto-Dev

**Data**: 7 de março de 2026
**Status**: Em Execução
**Objetivo**: Reduzir lentidão do VS Code, dividir em projetos independentes, remover referência "SHARED" de componentes

---

## 🎯 Estratégia Geral

### Fase 1: Mapeamento e Análise (Ollama GPU0+GPU1)
- Examinar 3548 arquivos Python
- Identificar dependências inter-componentes
- Criar índice de referências "SHARED"
- Dividir em **10 lotes de ~350 arquivos** cada

### Fase 2: Separação em Projetos Independentes
```
shared-auto-dev/                    (Orchestrador Principal)
├── specialized_agents/            (API + Message Bus)
├── btc-trading-agent/             (→ NOVO: crypto-trading-bot)
├── estou-aqui/                    (→ MANTÉM-SE)
├── homelab-copilot/               (→ NOVO: homelab-agent)
├── smartlife-integration/         (→ NOVO)
├── ad-interceptor/                (→ NOVO)
├── mcp-servers/                   (RAG + GitHub MCPs)
└── shared-libs/                   (Libs compartilhadas)
```

### Fase 3: Refatoração de Nomes (Remover "SHARED")
- **shared-copilot** → **auto-copilot** (extensão VS Code)
- **shared_tray_agent** → **system-tray-agent**
- **shared_agent/homelab_copilot_agent** → **homelab-agent**
- Todas as referências internas de "SHARED" → removidas

### Fase 4: Testes Organizados
```
tests/
├── unit/
│   ├── specialized_agents/
│   ├── trading_bot/
│   ├── homelab_agent/
│   ├── shared/
│   └── conftest.py
├── integration/
│   ├── trading_bot_live/
│   ├── homelab_connectivity/
│   ├── estou_aqui/
│   └── mcp_servers/
└── e2e/
    └── pipeline_tests/
```

---

## 📊 Componentes Identificados (10 Lotes)

| Lote | Arquivos | Componentes | Ação |
|------|----------|-------------|------|
| 1    | ~350     | btc_trading_agent, shared_tray_agent | Extrair → crypto-trading-bot |
| 2    | ~350     | homelab_copilot_agent, specialized_agents (core) | Extrair → homelab-agent |
| 3    | ~350     | estou-aqui/* | Validar + Manter | 
| 4    | ~350     | smartlife_integration, homeassistant_integration | Refatorar |
| 5    | ~350     | rag-mcp-server, github-mcp-server | Manter + Refatorar |
| 6    | ~350     | shared-copilot/src, pages | Renomear → auto-copilot |
| 7    | ~350     | tools/*, specialized_agents/* | Compartilhados |
| 8    | ~350     | scripts/*, deploy/*, site/* | Utilities |
| 9    | ~350     | agent_data/*, training_data/* | Dados+Testes |
| 10   | ~348     | Miscelânea, arquivos soltos | Limpar + Organizar |

---

## ⚙️ Uso de GPU (100% Ollama)

### GPU0 (RTX 2060) - :11434
- Análise de código Python
- Identificação de dependências
- Refatoração automática

### GPU1 (GTX 1050) - :11435
- Processamento de testes
- Análise de imports
- Validação de sintaxe

**Modelo**: `shared-coder` (paralelo em ambas as GPUs)

---

## 🔍 Fase 1: Análise de Lote 1 (btc_trading_agent)

**Arquivos**: 
- btc_trading_agent/*.py (~45 arquivos)
- shared_tray_agent/*.py (~15 arquivos)

**Tarefas**:
1. [ ] Analisar dependências com Ollama GPU0
2. [ ] Listar todas referências "SHARED/shared"
3. [ ] Verificar imports externos
4. [ ] Criar mapa de refatoração
5. [ ] Gerar testes unitários
6. [ ] Criar estrutura: `projects/crypto-trading-bot/`

---

## 🔗 Referências Mapeadas (Início)

### Buscar
- `shared_trading_agent` → `crypto_trading_agent`
- `EDDIE_*` → `CRYPTO_*` (env vars)
- `shared.trading` → `crypto_trading` (imports)
- "SHARED" em strings de log/config

### Manter (sem mudança)
- `estou-aqui/` (projeto independente)
- `rag-mcp-server/`, `github-mcp-server/`
- Libs em `tools/` (base compartilhada)

---

## 📋 Checklist de Execução

### Lote 1: btc_trading_agent
- [ ] GPU0: Analisar 60 arquivos
- [ ] GPU1: Validar sintaxe e testes
- [ ] Refatorar imports
- [ ] Criar tests/unit/crypto_trading_bot/
- [ ] Documentar mudanças

### Lote 2: homelab_copilot_agent
- [ ] GPU0: Analisar~80 arquivos
- [ ] GPU1: Analisar dependências
- [ ] Refatorar para homelab-agent
- [ ] Testes integrados

[... Lotes 3-10 seguem mesmo padrão ...]

---

## 🚀 Próximos Passos

1. **Agora**: Iniciar Lote 1 análise + refatoração
2. **Paralelo**: GPU1 processando testes
3. **Resultado**: Documento de mudanças + código refatorado
4. **Loop**: Continuar até Lote 10

---

**Versão**: 1.0
**Última atualização**: 7 de março de 2026 (Iniciado)
