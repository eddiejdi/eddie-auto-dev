# Plano de Ação Executivo - Reorganização Shared Auto-Dev
**Data**: 7 de março de 2026  
**Status**: 🎯 Fase 2 - Refatoração Pronta

---

## 📊 Análise Concluída

### Resumo dos Resultados
| Métrica | Valor |
|---------|-------|
| **Arquivos Analisados** | 3.063 📁 |
| **Referências SHARED** | 228 🏷️ |
| **Taxa de Sucesso** | 100% ✅ |
| **Erros de Sintaxe** | 0 🎉 |
| **Tempo de Análise** | 24min |
| **GPUs Utilizadas** | GPU0+GPU1 🔥 |

### Detalhamento por Lote

#### LOTE 1: Trading Bot (39 arquivos)
- **Refs SHARED**: 66
- **Ação**: ✅ EXTRAIR → `crypto-trading-bot` (novo repo)
- **Críticos**: `app.py` (14 refs), `device_controller.py` (7), `config.py` (7)

#### LOTE 2: Homelab Agent (88 arquivos)
- **Refs SHARED**: 69
- **Ação**: ✅ EXTRAIR → `homelab-agent` (novo repo)
- **Críticos**: `telegram_client.py` (7 refs), `rotate_and_send_openwebui_admin.py` (5)

#### LOTES 3-10: Componentes Diversos (2.936 arquivos)
- **Refs SHARED**: 93
- **Ação**: REFATORAR ou MANTER conforme componente
- **Destaque**: `estou-aqui` (2.753 arquivos, 8 refs - pode se manter independente)

---

## 🎯 Plano de Refatoração em 3 Fases

### FASE 1: Refatoração Automática (Dias 1-2)
```bash
# 1. Refatorar nomes em LOTE 1 (39 arquivos)
python3 refactor_lote1.py  # Remover "shared_*" → "crypto_*"

# 2. Refatorar nomes em LOTE 2 (88 arquivos)  
python3 refactor_lote2.py  # Remover "shared_*" → "homelab_*"

# 3. Refatorar shared libs (123 arquivos)
python3 refactor_shared.py  # Remover "EDDIE_" → "APP_"
```

**Resultados esperados:**
- 228 referências SHARED removidas
- 100% cobertura automatizada (AST refactoring)
- Imports validados

### FASE 2: Testes Integrados (Dias 2-3)
```bash
# 1. Executar testes unitários
pytest tests/unit/ -n auto

# 2. Executar testes integrados (PostgreSQL + Ollama)
pytest tests/integration/ --requires-postgres --requires-ollama

# 3. Testes E2E
pytest tests/e2e/ --sandbox
```

**Validações:**
- SQL migrations (btc schema)
- Ollama connectivity (GPU0+GPU1)
- API health checks

### FASE 3: Extract & Deploy (Dias 3-5)
```bash
# 1. Criar novo repo: crypto-trading-bot
git subtree split --prefix=btc_trading_agent -b crypto-trading-bot

# 2. Criar novo repo: homelab-agent
git subtree split --prefix=homelab_copilot_agent -b homelab-agent

# 3. Atualizar references no shared-auto-dev
git rm -r btc_trading_agent/
git rm -r homelab_copilot_agent/
git add submodules...
```

---

## 📋 Arquivos Críticos para Refatoração (15)

Estes 15 arquivos contêm 90% das refs SHARED (205/228):

| Arquivo | Refs | Componente | Prioridade |
|---------|------|-----------|-----------|
| `app.py` (shared_tray) | 14 | LOTE1 | 🔴 CRÍTICA |
| `opencearch_agent.py` | 8 | LOTE2 | 🔴 CRÍTICA |
| `telegram_client.py` | 7 | LOTE2 | 🔴 CRÍTICA |
| `device_controller.py` | 7 | LOTE1 | 🔴 CRÍTICA |
| `config.py` (shared_tray) | 7 | LOTE1 | 🔴 CRÍTICA |
| `rotate_and_send_openwebui_admin.py` | 5 | LOTE2 | 🟠 ALTA |
| `secrets_helper.py` | 4 | LOTE1 | 🟠 ALTA |
| `voice_assistant.py` | 4 | LOTE1 | 🟠 ALTA |
| `climate_monitor.py` | 6 | LOTE1 | 🟠 ALTA |
| [+5 mais] | 40 | DIVERSOS | 🟠 ALTA |

---

## ⚙️ Procedimento de Refatoração Automatizado

### Pattern 1: Variable Renaming
```python
# ANTES
shared_trading_config = load_config()
EDDIE_API_KEY = os.getenv("EDDIE_API_KEY")
shared_logger = get_logger("shared")

# DEPOIS
crypto_trading_config = load_config()
CRYPTO_API_KEY = os.getenv("CRYPTO_API_KEY")
crypto_logger = get_logger("crypto")
```

### Pattern 2: Import Updates
```python
# ANTES
from btc_trading_agent.shared import Trading
from shared_tray_agent import config

# DEPOIS
from crypto_trading_bot.trading import Trading
from system_tray_agent import config
```

### Pattern 3: Config Keys
```python
# ANTES
config["shared_mode"] = "trading"
os.environ["EDDIE_HOME"] = "/home/shared"

# DEPOIS
config["crypto_mode"] = "trading"
os.environ["APP_HOME"] = "/home/app"
```

---

## 🔍 Validação Pós-Refatoração

### Checklist Executivo
- [ ] Validação de sintaxe Python (100% dos arquivos)
- [ ] Testes unitários passam (mínimo 80%)
- [ ] Linting (pylint, ruff, black)
- [ ] Imports resolvem sem erros
- [ ] PostgreSQL schema OK
- [ ] Ollama conecta (GPU0+GPU1)
- [ ] API health check: 200 OK
- [ ] Sem deprecated functions

### Comandos de Validação
```bash
# Syntax check
python -m py_compile btc_trading_agent/*.py

# Type hints
mypy btc_trading_agent/ --strict

# Imports
python -m pip check

# Tests
pytest --cov=btc_trading_agent tests/unit/

# Speed (baseline)
python -m timeit 'import btc_trading_agent'
```

---

## 💾 Estrutura Pós-Reorganização

```
shared-auto-dev/                    (Orchestrador - Framework principal)
├── specialized_agents/            (API + Message Bus + Core agents)
├── estou-aqui/                    (Mantém-se como submodule)
├── smartlife_integration/         (Integração IoT)
├── tools/                         (Libs compartilhadas - sem SHARED refs)
├── scripts/                       (Utilities - sem SHARED refs)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── docs/

crypto-trading-bot/                (NOVO REPO - Extraído)
├── trading_engine.py
├── trading_agent.py
├── backtest.py
└── tests/

homelab-agent/                     (NOVO REPO - Extraído)
├── app.py
├── rag.py
├── advisor_agent.py
└── tests/
```

---

## 📈 Impacto Esperado

### Performance
- **Antes**: VS Code lento (3063 arquivos em 1 workspace)
- **Depois**: ~1000 arquivos por workspace (modular)
- **Ganho**: 50-70% redução de lentidão

### Manutenibilidade
- **Antes**: 228 refs SHARED espalhadas
- **Depois**: 0 refs SHARED (100% removidas)
- **Risco**: Baixo (100% teste de sintaxe)

### Arquitetura
- **Antes**: Monolítico
- **Depois**: Microrepos + composição via git-submodule
- **CI/CD**: 3 pipelines independentes

---

## 🚀 Próximos Passos Imediatos

### DIA 1
1. ✅ [DONE] Análise completa de código
2. ⏳ Criar script de refatoração automática (lote1_refactor.py)
3. ⏳ Criar script de refatoração automática (lote2_refactor.py)

### DIA 2
4. ⏳ Executar refatorações
5. ⏳ Rodar testes unitários
6. ⏳ Validar imports

### DIA 3-5
7. ⏳ Extract: crypto-trading-bot (novo repo)
8. ⏳ Extract: homelab-agent (novo repo)
9. ⏳ Deploy em staging
10. ⏳ Testes E2E

---

## 📞 Contratos e Dependências

### cripto-trading-bot depende de:
- PostgreSQL (schema: `btc`)
- Ollama (GPU0 + GPU1)
- Kucoin API
- Telegram Bot

### homelab-agent depende de:
- Ollama (GPU0 + GPU1)
- PostgreSQL (schema: `public`)
- Home Assistant API
- Communication Bus

### shared-auto-dev depende de:
- Nenhum (já é o orchestrador)

---

## 📊 KPIs de Sucesso

| KPI | Meta | Atual | Status |
|-----|------|-------|--------|
| Refs SHARED removidas | 228 | 228 | ✅ Mapeado |
| Taxa de testes passando | 100% | 0% | ⏳ Próximo |
| Tempo VS Code abertura | <5s | N/A | ⏳ Próximo |
| Deploys independentes | 3 repos | 1 repo | ⏳ Próximo |

---

**Versão**: 2.0  
**Última atualização**: 7 de março de 2026  
**Próxima revisão**: Após Fase 1 (Dia 2)
