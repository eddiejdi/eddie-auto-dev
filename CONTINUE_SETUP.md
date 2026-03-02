# Continue.dev Setup — VS Code + PyCharm

Implementar execução de comandos reais em ambas IDEs usando Ollama local + Eddie Tool Executor.

---

## 🚀 VS Code Setup

### 1. **Instalar extensão Continue.dev**

- Abra VS Code
- **Extensions** → Buscar `continue` 
- Instale **Continue - Code Autocompletion & Chat**
- Restart VS Code

### 2. **Configurar continue (automático)**

`~/.continue/config.yaml` já está configurado. Verifique:

```bash
cat ~/.continue/config.yaml | head -20
```

Deve conter:
- ✅ `apiBase: http://192.168.15.2:11434` (Ollama)
- ✅ `model: qwen3:8b` (com tool calling)
- ✅ `tools:` seção com shell_exec, read_file, etc.

### 3. **Usar no VS Code**

**Abrir Continue.dev:**
- `Ctrl+Shift+V` (Mac: `Cmd+Shift+V`) → Abre o chat
- Ou clique no ícone Continue na sidebar

**Fazer pergunta com tools:**

```
Qual o status do BTC trading agent?

// Continue deteta que precisa de tools → chama shell_exec automaticamente
// Executa: systemctl status btc-trading-agent
// Retorna resultado → responde em português
```

**Disponíveis também:**
```
/btc          → Status BTC agent + último trade
/docker       → Lista containers rodando
/health       → CPU, RAM, disco, uptime
/logs         → Ver logs do sistema
/git          → Git status, commits, etc.
```

---

## 🐍 PyCharm Setup

### 1. **Instalar Continue.dev no PyCharm**

- **Settings (Ctrl+Alt+S) → Plugins → Marketplace**
- Buscar `continue`
- Instale **Continue** (aquele com ícone azul/roxo)
- Restart PyCharm

### 2. **Configurar continue (manual)**

Continue no PyCharm usa outro local de config. Crie:

```bash
mkdir -p ~/.continue-pycharm
```

**Copie config.yaml para PyCharm:**

```bash
cp ~/.continue/config.yaml ~/.continue-pycharm/config.yaml
```

Ou, se PyCharm usar `~/.idea/continue/config.yaml`, crie:

```bash
mkdir -p ~/.idea/continue
cat > ~/.idea/continue/config.yaml << 'EOF'
name: Eddie Homelab AI
version: 1.0.0
schema: v1

models:
  - name: qwen3-tools
    provider: ollama
    model: qwen3:8b
    apiBase: http://192.168.15.2:11434
    title: "Qwen 3 8B (Tool Calling)"
    roles:
      - chat
    tools:
      - shell_exec
      - read_file
      - list_directory
      - system_info

tools:
  - name: eddie-tools
    type: custom
    apiBase: http://localhost:8503/llm-tools
    tools:
      - name: shell_exec
        description: "Execute shell commands"
        params:
          - name: command
            type: string
            required: true
      - name: read_file
        description: "Read file contents"
        params:
          - name: filepath
            type: string
            required: true
      - name: list_directory
        description: "List files and directories"
        params:
          - name: dirpath
            type: string
            required: true
      - name: system_info
        description: "Get system information"
        params: []
EOF
```

### 3. **Usar no PyCharm**

**Abrir Continue:**
- **Tools → Continue** (ou buscar "Continue" em Command Palette)
- Ou atalho customizado (Configure em Settings → Tools → Continue)

**Mesmos comandos do VS Code:**

```
Qual o status do docker?
/docker
/health
Resolve este erro: [erro do código]
```

---

## ⚙️ Configuração do executador (Eddie Tools API)

Para que as tools funcionem, certifique-se de que a API está rodando:

```bash
# No homelab
ssh homelab@192.168.15.2 "systemctl status specialized-agents-api"

# Ou localmente (dev)
cd /home/edenilson/eddie-auto-dev
source .venv/bin/activate
uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503 &
```

Verificar health:
```bash
curl http://localhost:8503/llm-tools/health
# { "status": "ok", "version": "1.0.0" }
```

---

## 🔧 Troubleshooting

### "Continue não encontra tools"
1. Verifique se `~/.continue/config.yaml` tem a seção `tools:`
2. Reinicie a IDE completamente
3. Verifique que Ollama está rodando: `curl http://192.168.15.2:11434/api/tags`

### "Tool execution timeout"
- Aumente timeout em `~/.continue/config.yaml` → `tools.timeout: 60` (segundos)
- Ou especifique no comando: `shell_exec(..., timeout=120)`

### "Permission denied"
- Tools só rodam comandos permitidos (whitelist)
- Ver allowed paths: `docker ps, systemctl, git, curl, journalctl, etc.`
- Comandos perigosos bloqueados: `rm -rf /, dd of=/dev, mkfs`

### "Connection refused: localhost:8503"
- API não está rodando
- Inicie: `python3 llm_tool_client.py` (inicia API também)
- Ou: `curl http://localhost:8503/health`

---

## 🧪 Teste rápido

### VS Code
```bash
# 1. Abrir Continue (Ctrl+Shift+V)
# 2. Digitar: /health
# 3. Continue deve mostrar:
#    CPU: 45% | RAM: 8GB / 32GB (25%) | Disk: 500GB / 2TB (25%) | Uptime: 5 days
```

### PyCharm
```bash
# 1. Tools → Continue
# 2. Digitar: qual o primeiro arquivo de /home?
# 3. Continue deve executar list_directory('/home') automaticamente
```

---

## 📚 Referência rápida

| Comando | Função |
|---------|--------|
| `/btc` | Status do trading agent BTC |
| `/docker` | Lista containers, logs, etc. |
| `/health` | Saúde do sistema (CPU, RAM, disco) |
| `/logs` | Ver journalctl filtrado |
| `/git` | Status, commits, branches |
| Pergunta normal | Tenta usar tools automaticamente |

---

## 🚀 Ativar no Cline (VS Code extension)

Se preferir usar **Cline** (ele também suporta tools):

1. Instale Cline no VS Code
2. Configure em **VS Code Settings → Cline**:
   ```json
   "cline.ollama.apiUrl": "http://192.168.15.2:11434",
   "cline.ollama.model": "qwen3:8b",
   "cline.tools.enabled": true,
   "cline.tools.editorTools": ["shell", "terminal"]
   ```
3. Agora Cline pode executar comandos via terminal

---

## ✅ Resumo

| IDE | Tool | Status | Atalho |
|-----|------|--------|--------|
| **VS Code** | Continue | ✅ Rodando | `Ctrl+Shift+V` |
| **VS Code** | Cline | ✅ Rodando | Command palette |
| **PyCharm** | Continue | ✅ Configurado | Tools menu |
| **PyCharm** | AI Assistant (nativo) | ❌ Sem tools | N/A |

Ambas IDEs estão prontas para usar Ollama local com execução de comandos reais! 🎉
