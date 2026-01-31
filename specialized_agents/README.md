# 🤖 Agentes Programadores Especializados

Sistema de agentes de IA especializados por linguagem de programação, cada um com seu próprio RAG, ambiente Docker isolado e integração com GitHub.

## 🎯 Características

- **8 Agentes Especializados**: Python, JavaScript, TypeScript, Go, Rust, Java, C#, PHP
- **RAG Próprio por Linguagem**: Base de conhecimento específica para cada linguagem
- **Containers Docker Isolados**: Cada projeto roda em seu próprio ambiente
- **Integração GitHub**: Push de código, criação de repos, PRs e issues
- **Upload/Download de Arquivos**: Suporte a arquivos individuais e projetos ZIP
- **Limpeza Automática**: Backup por 3 dias e exclusão automática de recursos não utilizados

## 📦 Estrutura

```
specialized_agents/
├── __init__.py           # Exports principais
├── config.py             # Configurações
├── base_agent.py         # Classe base dos agentes
├── language_agents.py    # Agentes por linguagem
├── rag_manager.py        # Gerenciador RAG por linguagem
├── docker_orchestrator.py # Orquestrador Docker
├── file_manager.py       # Gerenciador de arquivos
├── github_client.py      # Cliente GitHub
├── cleanup_service.py    # Serviço de limpeza
├── agent_manager.py      # Gerenciador central
├── streamlit_app.py      # Dashboard Streamlit
├── api.py                # API REST FastAPI
├── requirements.txt      # Dependências
├── install.sh            # Script de instalação
├── start.sh              # Script de inicialização
└── specialized-agents.service  # Systemd service
```

## 🚀 Instalação

```bash
# Clonar/acessar o diretório
cd ~/myClaude

# Dar permissão e executar instalação
chmod +x specialized_agents/install.sh
./specialized_agents/install.sh
```

## ⚡ Uso

### Dashboard Streamlit

```bash
./specialized_agents/start.sh
# Acesse: http://localhost:8502
```

### API REST

```bash
# Iniciar API
source venv/bin/activate
uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503

# Acesse docs: http://localhost:8503/docs
```

### Programático

```python
import asyncio
from specialized_agents import get_agent_manager

async def main():
    manager = get_agent_manager()
    await manager.initialize()
    
    # Criar projeto Python
    result = await manager.create_project(
        "python",
        "Crie uma API REST com FastAPI para gerenciar tarefas"
    )
    print(result)
    
    # Executar código
    result = await manager.execute_code(
        "python",
        'print("Hello World")'
    )
    print(result)

asyncio.run(main())
```

## 🐳 Docker

Cada linguagem usa uma imagem Docker específica:

| Linguagem | Imagem Base | Portas |
|-----------|-------------|--------|
| Python | python:3.12-slim | 8000-8100 |
| JavaScript | node:20-slim | 3000-3100 |
| TypeScript | node:20-slim | 3100-3200 |
| Go | golang:1.22-alpine | 4000-4100 |
| Rust | rust:1.75-slim | 4100-4200 |
| Java | eclipse-temurin:21-jdk | 8080-8180 |
| C# | dotnet/sdk:8.0 | 5000-5100 |
| PHP | php:8.3-cli | 9000-9100 |

## 🔧 Remote Orchestrator & Deploy

- Quando `REMOTE_ORCHESTRATOR_ENABLED=true`, o `AgentManager` usará `RemoteOrchestrator` ou `MultiRemoteOrchestrator` (faixa de hosts configurados em `REMOTE_ORCHESTRATOR_CONFIG['hosts']`).
- O orquestrador tenta hosts na ordem fornecida (ex.: `localhost` → `homelab`).
- **Atenção:** GitHub-hosted runners NÃO conseguem alcançar hosts em redes privadas (ex.: `192.168.*.*`). Se você pretende que o workflow faça SSH direto para seu homelab, instale um *self-hosted runner* no homelab e use `runs-on: [self-hosted]` no workflow.
- Alternativas: expor um endpoint seguro no homelab ou ter um agente no homelab que puxe mudanças do repositório.

## 📚 RAG

Cada agente tem sua própria coleção no ChromaDB:

```python
from specialized_agents.rag_manager import RAGManagerFactory

# RAG específico de Python
python_rag = RAGManagerFactory.get_manager("python")
await python_rag.index_code(code, "python", "descrição")
results = await python_rag.search("como usar FastAPI")

# Busca global em todas linguagens
results = await RAGManagerFactory.global_search("design patterns")
```

## 🐙 GitHub

```python
from specialized_agents import get_agent_manager

manager = get_agent_manager()

# Push projeto para GitHub
await manager.push_to_github(
    "python",
    "meu-projeto",
    repo_name="meu-repo",
    description="Meu projeto incrível"
)
```

## 🧹 Limpeza Automática

O sistema gerencia recursos automaticamente:

- **Backup**: 3 dias de retenção por padrão
- **Containers**: Removidos após 24h parados (com backup de logs)
- **Imagens**: Dangling images removidas automaticamente
- **Projetos**: Projetos inativos há 7+ dias são arquivados

```python
# Limpeza manual
report = await manager.run_cleanup()

# Ver status de armazenamento
storage = await manager.cleanup_service.get_storage_status()

# Restaurar backup
await manager.cleanup_service.restore_backup(backup_path)
```

## ⚙️ Configuração

Edite o arquivo `.env`:

```env
# Ollama
OLLAMA_HOST=http://192.168.15.2:11434
OLLAMA_MODEL=qwen2.5-coder:7b

# GitHub
GITHUB_TOKEN=ghp_xxxxx
GITHUB_AGENT_URL=http://localhost:8080
```

## 🔌 API Endpoints

### Agentes
- `GET /agents` - Lista agentes disponíveis
- `GET /agents/{language}` - Info do agente
- `POST /agents/{language}/activate` - Ativa agente

### Projetos
- `POST /projects/create` - Cria projeto
- `GET /projects/{language}` - Lista projetos
- `GET /projects/{language}/{name}/download` - Download ZIP

### Código
- `POST /code/generate` - Gera código
- `POST /code/execute` - Executa código
- `POST /code/analyze-error` - Analisa erro

### Docker
- `GET /docker/containers` - Lista containers
- `POST /docker/containers/{id}/start` - Inicia
- `POST /docker/containers/{id}/stop` - Para
- `DELETE /docker/containers/{id}` - Remove
- `POST /docker/exec` - Executa comando

### RAG
- `POST /rag/search` - Busca
- `POST /rag/index` - Indexa conteúdo

### GitHub
- `POST /github/push` - Push projeto
- `GET /github/repos` - Lista repos

### Limpeza
- `POST /cleanup/run` - Executa limpeza
- `GET /cleanup/storage` - Status armazenamento
- `GET /cleanup/backups` - Lista backups

## 📝 Systemd Service

```bash
# Copiar service
sudo cp specialized_agents/specialized-agents.service /etc/systemd/system/

# Habilitar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable specialized-agents
sudo systemctl start specialized-agents

# Ver logs
sudo journalctl -u specialized-agents -f
```

## 🛠️ Desenvolvimento

### Adicionar Nova Linguagem

1. Adicionar template em `config.py`:
```python
LANGUAGE_DOCKER_TEMPLATES["nova_lang"] = {
    "base_image": "...",
    "install_cmd": "...",
    ...
}
```

2. Criar classe do agente em `language_agents.py`:
```python
class NovaLangAgent(SpecializedAgent):
    def __init__(self):
        super().__init__("nova_lang")
    
    @property
    def name(self) -> str:
        return "Nova Lang Expert Agent"
    ...
```

3. Registrar no factory:
```python
AGENT_CLASSES["nova_lang"] = NovaLangAgent
```

## 📄 Licença

MIT License
