# 🎯 Guia Completo: Configuração PyCharm com MCP Servers do Homelab

Este guia ensina como configurar o PyCharm Professional para usar os MCP (Model Context Protocol) servers disponíveis no servidor homelab (192.168.15.2).

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Pré-requisitos](#pré-requisitos)
- [MCP Servers Disponíveis](#mcp-servers-disponíveis)
- [Configuração Passo a Passo](#configuração-passo-a-passo)
- [Uso no PyCharm](#uso-no-pycharm)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O homelab (`192.168.15.2`) possui 4 MCP servers ativos:

1. **GitHub MCP Server** - 35+ ferramentas para GitHub
2. **SSH Agent MCP** - Execução de comandos remotos via SSH
3. **RAG MCP Server** - Busca semântica com ChromaDB
4. **Homelab MCP Server** - Gerenciamento do servidor

Como PyCharm não tem suporte nativo para MCP (diferente do VS Code), usamos 3 estratégias:

- **External Tools** - Comandos rápidos no menu Tools
- **SSH Remote Interpreter** - Execução remota de código
- **Terminal Integration** - Scripts Python que invocam MCP servers

---

## 📦 Pré-requisitos

### 1. Acesso SSH ao Homelab

```bash
# Testar conexão
ssh homelab@192.168.15.2

# Copiar chave SSH (se necessário)
ssh-copy-id homelab@192.168.15.2
```

### 2. Verificar Inventário

```bash
# Executar inventário de MCP servers
cd /home/edenilson/shared-auto-dev
python3 scripts/inventory_homelab_mcp.py
```

Saída esperada:
```
✅ GITHUB - 35+ ferramentas para integração com GitHub
✅ SSH-AGENT - Execução de comandos SSH remotos
✅ RAG - Retrieval Augmented Generation
✅ HOMELAB - Gerenciamento do servidor homelab
```

### 3. Testar Integração

```bash
# Executar testes
python3 scripts/test_pycharm_mcp.py
```

---

## 🔧 MCP Servers Disponíveis

### 1️⃣ GitHub MCP Server

**Localização:** `/home/homelab/shared-auto-dev/github-mcp-server/src/github_mcp_server.py`

**Ferramentas principais:**
- `github_list_repos` - Listar repositórios
- `github_create_issue` - Criar issues
- `github_create_pr` - Criar Pull Requests
- `github_search_code` - Buscar código
- `github_trigger_workflow` - Disparar GitHub Actions
- E mais 30+ ferramentas...

**Execução via SSH:**
```bash
ssh homelab@192.168.15.2 'python3 /home/homelab/shared-auto-dev/github-mcp-server/src/github_mcp_server.py'
```

**Variáveis necessárias:**
- `GITHUB_TOKEN` - Token de acesso GitHub (no homelab)

---

### 2️⃣ SSH Agent MCP

**Localização:** `/home/homelab/shared-auto-dev/ssh_agent_mcp.py`

**Ferramentas principais:**
- `ssh_list_hosts` - Listar hosts SSH configurados
- `ssh_execute` - Executar comando em host remoto
- `ssh_test_connection` - Testar conexão SSH
- `ssh_get_system_info` - Obter informações do sistema
- `ssh_upload_file` / `ssh_download_file` - Transferência de arquivos

**Execução:**
```bash
ssh homelab@192.168.15.2 'cd /home/homelab/shared-auto-dev && python3 ssh_agent_mcp.py'
```

---

### 3️⃣ RAG MCP Server

**Localização:** `/home/homelab/shared-auto-dev/rag-mcp-server/src/rag_mcp_server.py`

**Ferramentas principais:**
- `rag_search` - Busca semântica em documentos
- `rag_index` - Indexar novos documentos
- `rag_list_collections` - Listar coleções disponíveis

**Dependências:**
- ChromaDB (instalado no homelab)

---

### 4️⃣ Homelab MCP Server

**Localização:** `/home/homelab/estou-aqui-deploy/scripts/homelab_mcp_server.py`

**Ferramentas:**
- Gerenciamento de containers Docker
- Status de serviços systemd
- Métricas do sistema

---

## ⚙️ Configuração Passo a Passo

### Passo 1: Configurar SSH Remote Interpreter

1. Abra PyCharm → **File** → **Settings** (ou **Ctrl+Alt+S**)
2. Navegue para: **Project** → **Python Interpreter**
3. Clique no ícone de engrenagem ⚙️ → **Add...**
4. Selecione **SSH Interpreter**
5. Configure:
   - **Host:** `192.168.15.2`
   - **Port:** `22`
   - **Username:** `homelab`
   - **Authentication:** SSH key (`~/.ssh/id_rsa`)
6. Selecione interpretador Python: `/home/homelab/shared-auto-dev/.venv/bin/python3`
7. Mapeamento de pastas:
   - **Local:** `/home/edenilson/shared-auto-dev`
   - **Remote:** `/home/homelab/shared-auto-dev`
8. Clique **OK**

Agora você pode executar scripts Python diretamente no homelab!

---

### Passo 2: Importar External Tools

Os External Tools já foram criados em `.idea/externalTools.xml`.

Para verificar/editar:

1. **Settings** → **Tools** → **External Tools**
2. Você verá:
   - ✅ **GitHub MCP - List Tools**
   - ✅ **GitHub MCP - Execute**
   - ✅ **SSH Agent MCP - List Hosts**
   - ✅ **RAG MCP - Search**
   - ✅ **Homelab - Docker PS**
   - ✅ **Homelab - System Info**
   - ✅ **MCP - Test All Servers**

**Uso:** Clique com botão direito em qualquer arquivo → **External Tools** → selecione ferramenta

---

### Passo 3: Configurar Run Configurations

Criar configurações de execução rápida para MCP servers:

#### GitHub MCP Server

1. **Run** → **Edit Configurations**
2. Clique **+** → **Python**
3. Configure:
   - **Name:** `GitHub MCP Server`
   - **Script path:** `/home/homelab/shared-auto-dev/github-mcp-server/src/github_mcp_server.py`
   - **Python interpreter:** `homelab@192.168.15.2 Python 3.12`
   - **Environment variables:** `GITHUB_TOKEN=...`
4. Clique **OK**

Repita para outros servidores MCP.

---

### Passo 4: Configurar Terminal SSH

Para terminal direto no homelab:

1. **Settings** → **Tools** → **Terminal**
2. **Shell path:** Configure para:
   ```bash
   ssh homelab@192.168.15.2
   ```

Ou crie um **Terminal Profile** dedicado:

1. **Settings** → **Tools** → **Terminal** → **Shell Integration**
2. Adicionar profile "Homelab SSH"

---

## 🚀 Uso no PyCharm

### Método 1: External Tools (Recomendado)

1. Clique com botão direito em qualquer arquivo do projeto
2. **External Tools** → selecione ferramenta MCP
3. Resultado aparece no painel **Run**

**Exemplo:**
- Selecione `Homelab - Docker PS` para ver containers rodando

### Método 2: Run Configurations

1. Clique no dropdown de Run Configurations (topo direito)
2. Selecione `GitHub MCP Server` (ou outro)
3. Clique em **Run** ▶️

### Método 3: Terminal Integration

```python
# Criar script: scripts/mcp_helper.py
import subprocess

def call_github_mcp(tool_name, **params):
    """Chama uma ferramenta do GitHub MCP Server"""
    cmd = [
        "ssh", "homelab@192.168.15.2",
        f"python3 /home/homelab/shared-auto-dev/github-mcp-server/src/github_mcp_server.py",
    ]
    # ... implementação
    
# Uso no Terminal PyCharm:
from scripts.mcp_helper import call_github_mcp
result = call_github_mcp("github_list_repos", owner="eddiejdi")
print(result)
```

### Método 4: Python Console Remoto

1. **Tools** → **Python or Debug Console**
2. Console conecta via SSH ao homelab
3. Importar e usar MCP servers diretamente:

```python
import sys
sys.path.insert(0, '/home/homelab/shared-auto-dev')

# Usar GitHub MCP
from github_mcp_server import github_list_repos
repos = github_list_repos(owner="eddiejdi")

# Usar RAG MCP
from rag_mcp_server import rag_search
results = rag_search(query="Docker configuration", collection="homelab")
```

---

## 📊 Arquivo de Configuração Gerado

Localização: `.idea/mcp-servers.json`

```json
{
  "version": "1.0",
  "mcp_servers": {
    "github": {
      "command": "ssh",
      "args": [
        "homelab@192.168.15.2",
        "python3",
        "/home/homelab/shared-auto-dev/github-mcp-server/src/github_mcp_server.py"
      ],
      "transport": "stdio",
      "description": "GitHub MCP Server - 35+ ferramentas",
      "category": "development"
    },
    "ssh-agent": {
      "command": "ssh",
      "args": [
        "homelab@192.168.15.2",
        "python3",
        "/home/homelab/shared-auto-dev/ssh_agent_mcp.py"
      ],
      "transport": "stdio",
      "description": "SSH Agent MCP",
      "category": "infrastructure"
    }
    // ... mais servidores
  },
  "ssh_config": {
    "host": "192.168.15.2",
    "user": "homelab",
    "key_file": "~/.ssh/id_rsa"
  }
}
```

---

## 🔍 Troubleshooting

### Problema: "SSH connection refused"

**Solução:**
```bash
# Verificar conectividade
ssh homelab@192.168.15.2 echo "OK"

# Verificar serviço SSH no homelab
ssh homelab@192.168.15.2 'sudo systemctl status ssh'
```

### Problema: "ModuleNotFoundError: No module named 'mcp'"

**Solução:**
```bash
# Instalar dependências MCP no homelab
ssh homelab@192.168.15.2 'cd /home/homelab/shared-auto-dev && source .venv/bin/activate && pip install mcp httpx'
```

### Problema: "Permission denied (publickey)"

**Solução:**
```bash
# Copiar chave SSH
ssh-copy-id homelab@192.168.15.2

# Ou especificar chave manualmente
ssh -i ~/.ssh/id_rsa homelab@192.168.15.2
```

### Problema: "GITHUB_TOKEN not found"

**Solução:**
```bash
# Adicionar token ao homelab
ssh homelab@192.168.15.2
echo 'export GITHUB_TOKEN="ghp_..."' >> ~/.bashrc
source ~/.bashrc
```

### Problema: External Tools não aparecem

**Solução:**
1. Verificar se `.idea/externalTools.xml` existe
2. Reiniciar PyCharm
3. **File** → **Invalidate Caches / Restart**

---

## 📚 Recursos Adicionais

### Scripts Úteis

| Script | Descrição |
|--------|-----------|
| `scripts/inventory_homelab_mcp.py` | Inventariar MCP servers disponíveis |
| `scripts/test_pycharm_mcp.py` | Testar integração MCP |
| `test_ssh_tools.py` | Testar SSH Agent MCP |

### Documentação Relacionada

- [HOMELAB_AGENT.md](../docs/HOMELAB_AGENT.md) - Agente Homelab completo
- [copilot-instructions.md](../.github/copilot-instructions.md) - Instruções gerais
- [github-mcp-server/README.md](../github-mcp-server/README.md) - GitHub MCP detalhado

### Atalhos PyCharm Úteis

| Atalho | Ação |
|--------|------|
| `Ctrl+Alt+S` | Abrir Settings |
| `Alt+F12` | Abrir Terminal |
| `Shift+F10` | Run current configuration |
| `Ctrl+Shift+A` | Find Action (buscar External Tools) |

---

## ✅ Checklist de Configuração

- [ ] SSH configurado e testado (`ssh homelab@192.168.15.2`)
- [ ] Python Remote Interpreter adicionado (Settings → Project → Python Interpreter)
- [ ] External Tools verificados (Settings → Tools → External Tools)
- [ ] Arquivo `.idea/mcp-servers.json` gerado
- [ ] Teste executado com sucesso (`python3 scripts/test_pycharm_mcp.py`)
- [ ] Run Configurations criadas para MCP servers favoritos
- [ ] Terminal SSH profile configurado (opcional)

---

## 🎯 Próximos Passos

1. **Explorar GitHub MCP Server:**
   - Listar seus repositórios
   - Criar issues automaticamente
   - Buscar código

2. **Usar RAG MCP:**
   - Indexar documentação do projeto
   - Fazer buscas semânticas

3. **Automatizar com SSH Agent MCP:**
   - Deploy automático via SSH
   - Monitoramento de servidores

4. **Integrar com Ollama:**
   - Usar modelos LLM do homelab (porta 11434)
   - Gerar código com AI assistida

---

## 📞 Suporte

Se encontrar problemas:

1. Execute diagnóstico: `python3 scripts/test_pycharm_mcp.py`
2. Verifique logs do homelab: `ssh homelab@192.168.15.2 'journalctl -n 50'`
3. Consulte [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)

---

**Última atualização:** 2026-02-25  
**Versão:** 1.0  
**Autor:** Shared Auto-Dev System

