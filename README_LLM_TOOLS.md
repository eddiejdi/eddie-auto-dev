# 🧠 LLM Tool Executor - Terminal Access para Modelos Locais

O Copilot do GitHub tem acesso ao terminal. Agora seu **LLM Ollama local também tem!**

## ⚡ Quick Start (30 segundos)

### 1. Executar Setup
```bash
cd /home/edenilson/eddie-auto-dev
./setup_llm_tools.sh
```

Isso irá:
- ✓ Verificar Ollama e API
- ✓ Criar modelo customizado `eddie-tools`
- ✓ Testar endpoints
- ✓ Preparar scripts

### 2. Usar no Terminal (Modo Interativo)
```bash
python3 llm_tool_client.py --interactive --model eddie-tools
```

Exemplo de sessão:
```
Você> qual é o status do git?
🤖 Processando...

🔧 Executando ferramenta: shell_exec
✅ shell_exec executado com sucesso

🤖 Assistente: O repositório está limpo. Branch: main
          Não há alterações pendentes.
```

### 3. Usar via URL Direta (Query Única)
```bash
python3 llm_tool_client.py "list files in /home" --model eddie-tools
```

## 📡 API Endpoints

| Endpoint | Descrição |
|----------|-----------|
| `GET /llm-tools/available` | Listar ferramentas |
| `POST /llm-tools/exec-shell` | Executar comando |
| `POST /llm-tools/read-file` | Ler arquivo |
| `POST /llm-tools/list-directory` | Listar diretório |
| `GET /llm-tools/system-info` | Info do sistema |
| `GET /llm-tools/health` | Health check |

### Exemplos de Uso
```bash
# Executar comando
curl -X POST http://localhost:8503/llm-tools/exec-shell \
  -H 'Content-Type: application/json' \
  -d '{"command":"git status"}'

# Ler arquivo
curl -X POST http://localhost:8503/llm-tools/read-file \
  -H 'Content-Type: application/json' \
  -d '{"filepath":"/etc/hostname"}'

# Info do sistema
curl http://localhost:8503/llm-tools/system-info
```

## 🎯 Casos de Uso

### ✅ Debugging Automático
```
Você> por que o Docker não levanta?
🤖 Deixa eu verificar...

[Executa: docker logs my-service]
[Lê: /var/log/docker.log]
[Roda: docker ps]

🤖 Assistente: O problema é a porta 8080 já em uso. 
Tente: docker run -p 9000:8080 ...
```

### ✅ Code Analysis
```
Você> analisa este projeto
🤖 Deixa eu dar uma olhada...

[Lê: package.json]
[Lê: src/main.py]
[Roda: git log --oneline]

🤖 Assistente: Projeto Node.js com 3 cores, última atualização...
```

### ✅ System Monitoring
```
Você> como está a saúde do servidor?
🤖 Verificando...

[Executa: system_info]
[Roda: df -h]
[Roda: top -bn1]

🤖 Assistente: CPU: 45%, Memória: 62%, Disco: 1.2TB/2TB
```

## 🔧 Ferramentas Disponíveis

### shell_exec
Executa comandos shell com whitelist de segurança.

**Categorias permitidas:**
- `development`: git, docker, python, npm, pytest, etc
- `system_info`: uname, ps, df, uptime, etc
- `files`: ls, cat, grep, find, cp, mv, etc
- `network`: curl, wget, ping, ssh, etc
- `database`: psql, mysql, redis-cli, etc

**Bloqueios de segurança:**
- ❌ `rm -rf /` (deletar raiz)
- ❌ `dd of=/dev/sda` (sobrescrever discos)
- ❌ `mkfs` (formatar)
- ❌ `chmod 777 /` (permissões perigosas)

### read_file
Lê arquivos de texto (máx 10 MB).

**Paths permitidos:**
- `/home`
- `/tmp`
- `/root`
- `/opt`

### list_directory
Lista conteúdo de diretórios.

### system_info
Retorna:
- Platform, release, hostname
- CPU usage percentual
- Memória disponível e total
- Uso de disco

## 🛠️ Configurar Modelo Customizado

### Opção 1: Usando o Modelfile Incluído
```bash
cd models
ollama create eddie-tools -f Modelfile.eddie-tools
ollama run eddie-tools
```

### Opção 2: Criar Seu Próprio
```dockerfile
FROM qwen2.5-coder:7b

SYSTEM """You have access to shell execution tools:
- shell_exec: Run commands
- read_file: Read files
- list_directory: List dirs
- system_info: System info

When using tools, respond with:
<TOOL_USE>
{
  "tool": "shell_exec",
  "params": {"command": "your command"}
}
</TOOL_USE>"""

PARAMETER temperature 0.7
PARAMETER num_ctx 16384
```

Então:
```bash
ollama create my-tools -f Modelfile
```

## 📊 Exemplos Completos

### Exemplo 1: Deploy Checker
```bash
python3 llm_tool_client.py \
  "verificar se meu app está rodando, logs, e saúde" \
  --model eddie-tools
```

Resultado:
```
🔧 Executando ferramenta: shell_exec (docker ps)
🔧 Executando ferramenta: shell_exec (docker logs my-app | tail)
🔧 Executando ferramenta: read_file (/var/log/app.log)

🤖 Assistente: Seu app está rodando (container ID: abc123)
Memória: 512MB, CPU: 15%
Últimas linhas do log mostram status OK.
Última atualização: 2 horas atrás.
```

### Exemplo 2: Git Analysis
```bash
python3 llm_tool_client.py \
  "fazer uma análise completa do repositório git" \
  --model eddie-tools
```

Resultado:
```
🔧 Executando: git status
🔧 Executando: git log --oneline
🔧 Lendo: README.md
🔧 Executando: git branch -a

🤖 Assistente: 
- Repositório em main branch, limpo
- 42 commits, último de 3 dias atrás
- 3 branches locais + 5 remotas
- README.md está atualizado
- Recomendação: fazer merge de feature/* para main
```

## 🚀 Integração OpenWebUI

Se estiver usando OpenWebUI em `http://localhost:3000`:

1. Adicione no modelo system prompt:
```
You have access to shell tools at http://localhost:8503/llm-tools/

Use them when needed:
<TOOL_USE>{"tool": "shell_exec", "params": {"command": "YOUR_COMMAND"}}
</TOOL_USE>
```

2. Registre no OpenWebUI como função de suporte

## 🔒 Segurança

### Considerações Importantes

1. **Rede Local Apenas**: Use em redes confiáveis
2. **Firewall**: Bloqueie acesso externo à porta 8503
3. **Audit Log**: Todos os comandos são logados em `logs/`
4. **Whitelist**: Apenas comandos pré-aprovados rodam
5. **Permissões**: Execute como user apropriado (não root)

### Em Produção

```bash
# Rodas em docker com resource limits
docker run -d \
  --cpus="1.5" \
  --memory="2g" \
  -p 8503:8503 \
  eddie-auto-dev

# Ou com systemd usuario
sudo systemctl --user start eddie-llm-tools
```

## 📝 Logs

Ver o que o LLM executou:
```bash
tail -f logs/llm-tools.log
```

Exemplo de output:
```
2026-03-01 16:30:45 - LLM-Tools - INFO - [LLM-Tools] POST /llm-tools/exec-shell from 127.0.0.1
2026-03-01 16:30:45 - llm_tool_executor - INFO - Shell exec: git status
2026-03-01 16:30:46 - llm_tool_executor - INFO - Command executed: exit_code=0, duration=125ms
```

## 🐛 Troubleshooting

### Erro: "API não está rodando"
```bash
# Inicie a API
uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503
```

### Erro: "Comando não permitido"
O comando está fora da whitelist. Use um alternativo autorizado.

### Timeout nos comandos
Aumente o timeout (máximo 300s):
```python
{"command": "long-running-command", "timeout": 120}
```

### Modelo não responde
Verifique se `eddie-tools` foi criado:
```bash
ollama list | grep eddie-tools
```

Se não existir:
```bash
cd models
ollama create eddie-tools -f Modelfile.eddie-tools
```

## 📚 Documentação Completa

Para detalhes técnicos, veja:
```bash
cat docs/LLM_TOOL_EXECUTOR.md
```

## 🎓 Próximos Passos

1. **Experimente com Seu Projeto**
   ```bash
   python3 llm_tool_client.py "analisa meu projeto" --model eddie-tools
   ```

2. **Crie Scripts Personalizados**
   - Usar `llm_tool_client.py` como biblioteca Python
   - Integrar com seus workflows

3. **Ajuste Segurança**
   - Editar `ALLOWED_COMMANDS` em `llm_tool_executor.py`
   - Adicionar seus próprios comandos seguros

4. **Monitore Performance**
   - Ver `/llm-tools/health`
   - Ajustar timeouts e limites

## 💡 Dicas

✅ **Bom**: "compile este código e mostra os erros"
❌ **Ruim**: "lista tudo no /root" (fora do escopo autorizado)

✅ **Bom**: "verifica a saúde dos containers"
❌ **Ruim**: "remove tudo" (perigoso)

## 🤝 Suporte

Bugs ou sugestões? Abra issue no GitHub.

---

**Criado com ❤️ por Eddie Auto-Dev**

Agora seu LLM tem superpoderes! 🚀
