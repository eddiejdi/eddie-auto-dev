# 🚀 PyCharm MCP Integration - Quick Start

Configuração rápida para usar MCP servers do homelab no PyCharm.

## ⚡ Setup Rápido (5 minutos)

### 1. Verificar SSH
```bash
ssh homelab@192.168.15.2 echo "OK"
```

### 2. Executar Inventário
```bash
python3 scripts/inventory_homelab_mcp.py
```

### 3. Testar Integração
```bash
python3 scripts/test_pycharm_mcp.py
```

### 4. Configurar PyCharm

**Settings → Project → Python Interpreter → Add SSH Interpreter:**
- Host: `192.168.15.2`
- User: `homelab`
- Interpreter: `/home/homelab/shared-auto-dev/.venv/bin/python3`

**Settings → Tools → External Tools:**
- Já configurados em `.idea/externalTools.xml`
- Acesse: Botão direito → External Tools

## 📦 MCP Servers Disponíveis

| Servidor | Ferramentas | Categoria |
|----------|-------------|-----------|
| **GitHub MCP** | 35+ ferramentas GitHub (repos, issues, PRs, actions) | Development |
| **SSH Agent MCP** | Execução remota de comandos via SSH | Infrastructure |
| **RAG MCP** | Busca semântica com ChromaDB | AI |
| **Homelab MCP** | Gerenciamento Docker/systemd | Infrastructure |

## 🎯 Uso Rápido

### Python Console (Recomendado)

```python
# Importar helper
from scripts.mcp_helper import GitHubMCP, SSHAgentMCP, RAGMCP, quick_ssh

# GitHub - Listar repositórios
github = GitHubMCP()
repos = github.list_repos(owner="eddiejdi")

# SSH - Executar comando
output = quick_ssh("docker ps")
print(output)

# RAG - Buscar documentação
from scripts.mcp_helper import quick_rag_search
docs = quick_rag_search("como configurar MCP")
```

### External Tools

1. Botão direito no projeto
2. **External Tools** → selecione:
   - `GitHub MCP - List Tools`
   - `Homelab - Docker PS`
   - `Homelab - System Info`
   - `MCP - Test All Servers`

### Terminal SSH

```bash
# Executar via SSH
ssh homelab@192.168.15.2 'docker ps'
ssh homelab@192.168.15.2 'python3 /home/homelab/shared-auto-dev/test_ssh_tools.py'
```

## 📁 Arquivos Criados

```
.idea/
  ├── mcp-servers.json      # Configuração MCP servers
  └── externalTools.xml     # External Tools do PyCharm

docs/
  └── PYCHARM_MCP_SETUP.md  # Guia completo

scripts/
  ├── inventory_homelab_mcp.py  # Inventário de servidores
  ├── test_pycharm_mcp.py       # Testes de integração
  └── mcp_helper.py             # Helper Python para MCP
```

## 🔧 Troubleshooting

### "SSH connection refused"
```bash
# Testar SSH
ssh homelab@192.168.15.2
```

### "Module not found"
```bash
# Instalar no homelab
ssh homelab@192.168.15.2 'cd /home/homelab/shared-auto-dev && source .venv/bin/activate && pip install mcp httpx paramiko'
```

### External Tools não aparecem
1. **File** → **Invalidate Caches / Restart**
2. Verificar `.idea/externalTools.xml` existe

## 📖 Documentação Completa

Ver: [docs/PYCHARM_MCP_SETUP.md](../docs/PYCHARM_MCP_SETUP.md)

## ✅ Checklist

- [ ] SSH configurado (`ssh homelab@192.168.15.2`)
- [ ] Inventário executado (`python3 scripts/inventory_homelab_mcp.py`)
- [ ] Testes passando (`python3 scripts/test_pycharm_mcp.py`)
- [ ] Remote Interpreter configurado (Settings → Python Interpreter)
- [ ] External Tools verificados (Settings → Tools → External Tools)

## 🎓 Exemplos Práticos

### Exemplo 1: Listar Containers Docker
```python
from scripts.mcp_helper import quick_ssh
containers = quick_ssh("docker ps --format '{{.Names}}'")
print(containers)
```

### Exemplo 2: Criar Issue no GitHub
```python
from scripts.mcp_helper import GitHubMCP

github = GitHubMCP()
result = github.create_issue(
    repo="shared-auto-dev",
    title="Bug: Login não funciona",
    body="Descrição detalhada do bug..."
)
print(result)
```

### Exemplo 3: Buscar Documentação
```python
from scripts.mcp_helper import quick_rag_search

docs = quick_rag_search("como usar Docker compose", collection="homelab")
for doc in docs:
    print(doc['content'][:200])
```

---

**Última atualização:** 2026-02-25  
**Status:** ✅ Implementado e testado

