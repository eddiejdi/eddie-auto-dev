# Quick Start — Continue.dev com Eddie Tools

## ✅ Status Atual

| Componente | Status |
|-----------|--------|
| **VS Code** | ✅ Configurado |
| **PyCharm** | ✅ Configurado |
| **Ollama** | ✅ Rodando (192.168.15.2:11434) |
| **API Eddie Tools** | Pronto para rodar |

---

## 🚀 Para começar agora

### VS Code

```bash
# 1. Abrir VS Code
code /home/edenilson/eddie-auto-dev

# 2. No VS Code:
#    Instale extensão: "Continue" (marketplace)
#    Ou: Extensões → Pesquise "Continue" → Instale

# 3. Pressione: Ctrl+Shift+V
#    (abre o painel Continue.dev)

# 4. Digite uma pergunta:
"qual o status do docker?"

# Continue vai:
# ✅ Detectar que precisa executar comando
# ✅ Chamar shell_exec("docker ps") via API
# ✅ Retornar resultado
# ✅ Responder em linguagem natural
```

### PyCharm

```bash
# 1. Abrir PyCharm
pycharm-community /home/edenilson/eddie-auto-dev

# 2. No PyCharm:
#    Instale plugin: "Continue" (Marketplace)

# 3. Tools → Continue
#    (ou pesquise "Continue" em Command Palette)

# 4. Mesmas perguntas do VS Code funcionam!
```

---

## 🧪 Testes rápidos

### Teste 1: System Info

```
Prompt: "qual o uso de CPU e memória agora?"

Esperado:
🤖 Continue detecta que precisa de system_info
   Executa: system_info()
   Retorna: CPU 45% | RAM 8GB/32GB (25%) | Disk 500GB/2TB (25%)
   Resposta: "Seu sistema está usando 45% de CPU..."
```

### Teste 2: Docker Status

```
Prompt: "/docker"

Esperado:
🤖 Executa: shell_exec("docker ps")
   Retorna: Lista de containers rodando
   Resposta: "Existem X containers rodando..."
```

### Teste 3: File Reading

```
Prompt: "mostra o começo do arquivo ~/.bashrc"

Esperado:
🤖 Executa: read_file("/home/edenilson/.bashrc", max_lines=20)
   Retorna: Conteúdo do arquivo
   Resposta: "Aqui está o começo do arquivo..."
```

---

## 🔧 Se algo não funcionar

### Continue não aparece em VS Code
```bash
# Reinstale:
# 1. Extensions → Desinstale Continue
# 2. Marketplace → Instale novamente
# 3. Reload VS Code (Ctrl+R)
```

### Continue não executa comandos
```bash
# Verifique se API está rodando:
curl http://localhost:8503/llm-tools/available

# Se não responder, inicie:
cd /home/edenilson/eddie-auto-dev
source .venv/bin/activate
uvicorn specialized_agents.api:app --port 8503 &

# Teste a tool diretamente:
curl -X POST http://localhost:8503/llm-tools/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool_name":"system_info","params":{}}'
```

### Ollama não responde
```bash
# SSH para homelab:
ssh homelab@192.168.15.2
systemctl status ollama
# Se parado: systemctl start ollama

# Ou se estiver rodando manualmente:
# ollama serve &
```

---

## 📚 Comandos disponíveis via slash

| Comando | Função |
|---------|--------|
| `/health` | CPU, RAM, disco, uptime |
| `/docker` | Docker containers, logs, inspect |
| `/btc` | BTC trading agent status + último trade |
| `/logs` | Ver journalctl (system logs) |
| `/git` | Git status, commits, branches |

---

## 🎯 Fluxo típico

```
Usuário no VS Code/PyCharm
    ↓
Abre Continue (Ctrl+Shift+V ou Tools → Continue)
    ↓
Digita pergunta: "qual o status do BTC?"
    ↓
Continue.dev análisa
    ↓
Detecta que precisa tool: shell_exec + read_file + system_info
    ↓
Chama API (http://localhost:8503/llm-tools/execute)
    ↓
Eddie Tools Executor executa
    ↓
Retorna resultado
    ↓
Continue.dev integra no contexto do Ollama
    ↓
Ollama (qwen3:8b) gera resposta em português
    ↓
Resultado exibido no chat
```

---

## 📊 Comparação: Antes vs Depois

| Cenário | Antes | Depois |
|---------|-------|--------|
| "status do docker?" | Instrui como rodar `docker ps` | Executa automaticamente |
| Visualizar logs | Copia comandos manualmente | Executa `journalctl` direto |
| Checar saúde do sistema | Pede para rodar comandos | Mostra CPU/RAM/Disk em tempo real |
| Ler arquivo | Pede para abrir manualmente | Lê diretamente via API |

---

## ✨ Diferencial

- ✅ **Execução real** não alucinação
- ✅ **Segurança** whitelist de comandos + paths
- ✅ **Aprendizado** rememoriza decisões passadas
- ✅ **Transparência** todas as queries são logadas
- ✅ **Compatibilidade** funciona em VS Code, PyCharm, Terminal, Open WebUI

---

## 📞 Suporte

Se precisar refazer o setup:

```bash
bash /home/edenilson/eddie-auto-dev/setup_continue.sh
```

Documentação completa:
- [CONTINUE_SETUP.md](CONTINUE_SETUP.md)
- [docs/LLM_TOOL_CALLING.md](docs/LLM_TOOL_CALLING.md)

**Tudo configurado! 🎉 Aproveite as tools.**
