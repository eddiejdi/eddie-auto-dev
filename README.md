# 🤖 Eddie Auto-Dev System

[![Agent Responder Integration Test](https://github.com/eddiejdi/eddie-auto-dev/actions/workflows/integration-agent-responder.yml/badge.svg)](https://github.com/eddiejdi/eddie-auto-dev/actions/workflows/integration-agent-responder.yml)

Sistema completo de auto-desenvolvimento com IA, integrando Telegram Bot, Ollama LLM, e Agentes Especializados por linguagem.

## ✨ Recursos

- 🤖 **Bot Telegram** - Interface de chat com IA
- 🧠 **Ollama LLM** - Modelo eddie-coder para geração de código
- 🔍 **Busca Web** - Pesquisa automática para enriquecer respostas
- 🛠️ **8 Agentes Especializados** - Python, JS, TS, Go, Rust, Java, C#, PHP
- 📚 **RAG** - Retrieval Augmented Generation com ChromaDB
- 🐳 **Docker** - Ambientes isolados por projeto
- 🔄 **CI/CD** - GitHub Actions para deploy automático
- 🔒 **ESM Maintenance** - script e documentação para ativar Ubuntu Pro/ESM no homelab (veja `docs/ESM_ACTIVATION_HOMELAB.md` e `scripts/enable_esm_homelab.sh`)

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/eddiejdi/myClaude.git
cd myClaude

# 2. Configure
cp .env.example .env
# Edite .env com seus tokens

# 3. Inicie
./start_api.sh
python3 telegram_bot.py
## 🎯 Diretor (OpenWebUI)

Para iniciar a função do diretor via venv local:

```bash
./run_director.sh
## 📚 Documentação

| Documento | Descrição |
|-----------|-----------|
| [README](docs/README.md) | Documentação completa |
| [ESM_ACTIVATION_HOMELAB](docs/ESM_ACTIVATION_HOMELAB.md) | Passo a passo para ativar ESM no homelab |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Arquitetura do sistema |
| [SETUP](docs/SETUP.md) | Guia de configuração |
| [API](docs/API.md) | Referência da API |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | Solução de problemas |

## 🏗️ Arquitetura

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Telegram   │───▶│  Bot Python │───▶│   Ollama    │
│    App      │    │   (async)   │    │  LLM :11434 │
└─────────────┘    └──────┬──────┘    └─────────────┘
                          │
                          ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Web Search  │◀───│AutoDeveloper│───▶│ Agents API  │
│ DuckDuckGo  │    │   Class     │    │    :8503    │
└─────────────┘    └─────────────┘    └─────────────┘
## 🔧 Serviços

```bash
# Bot Telegram
sudo systemctl status eddie-telegram-bot

# API Agentes
sudo systemctl status specialized-agents

# Ver logs
journalctl -u eddie-telegram-bot -f
## 📡 API Endpoints

```bash
# Health
GET /health

# Agentes
GET /agents
GET /agents/{language}
POST /agents/{language}/activate

# Projetos
POST /projects/create
GET /projects/{language}

# Código
POST /code/generate
POST /code/execute

# RAG
POST /rag/search
POST /rag/index

# GitHub
POST /github/push
## 📁 Estrutura

myClaude/
├── telegram_bot.py      # Bot principal
├── web_search.py        # Busca web
├── docs/                # Documentação
├── specialized_agents/  # Agentes por linguagem
├── solutions/           # Soluções geradas
├── chroma_db/           # Base RAG
└── .github/workflows/   # CI/CD
## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Add nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

MIT License - Eddie Homelab © 2026
