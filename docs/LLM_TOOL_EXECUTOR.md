# LLM Tool Executor - Terminal & File Access para Modelo Local

Permite que modelos LLM locais (Ollama) executem comandos no terminal, leiam arquivos e acessem informações do sistema, similar ao **function calling do GitHub Copilot**.

## 🎯 Uso Rápido

### 1. Listar Ferramentas Disponíveis

```bash
curl http://localhost:8503/llm-tools/available
```

Resposta:
```json
{
  "tools": [
    {
      "name": "shell_exec",
      "description": "Executar comando shell no terminal",
      "parameters": {
        "command": "str - comando a executar",
        "timeout": "int - timeout em segundos (default 30)"
      }
    },
    {
      "name": "read_file",
      "description": "Ler conteúdo de arquivo"
    },
    {
      "name": "list_directory",
      "description": "Listar arquivos e diretórios"
    },
    {
      "name": "system_info",
      "description": "Obter informações do sistema"
    }
  ]
}
```

### 2. Executar Comando Shell

```bash
curl -X POST http://localhost:8503/llm-tools/exec-shell \
  -H 'Content-Type: application/json' \
  -d '{
    "command": "git status",
    "cwd": "/home/user/project",
    "timeout": 30
  }'
```

Resposta:
```json
{
  "success": true,
  "stdout": "On branch main\nnothing to commit...",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 125.45,
  "timestamp": "2026-03-01T16:30:00.000000",
  "category": "development"
}
```

### 3. Ler Arquivo

```bash
curl -X POST http://localhost:8503/llm-tools/read-file \
  -H 'Content-Type: application/json' \
  -d '{
    "filepath": "/etc/hostname",
    "max_lines": 100
  }'
```

### 4. Listar Diretório

```bash
curl -X POST http://localhost:8503/llm-tools/list-directory \
  -H 'Content-Type: application/json' \
  -d '{
    "dirpath": "/home/user/project",
    "recursive": false
  }'
```

### 5. Obter Informações do Sistema

```bash
curl http://localhost:8503/llm-tools/system-info
```

## 🔒 Segurança

### Whitelist de Comandos

Apenas os seguintes comandos são permitidos por categoria:

- **system_info**: `uname`, `lsb_release`, `hostnamectl`, `uptime`, `whoami`, `pwd`, `date`, `env`, `systemctl`, `journalctl`, `ps`, `top`, `free`, `df`, `du`, `lsblk`, `ip`, `netstat`, `ss`, `ifconfig`
- **files**: `ls`, `cat`, `head`, `tail`, `grep`, `find`, `wc`, `file`, `stat`, `tree`, `chmod`, `chown`, `mkdir`, `rm`, `cp`, `mv`
- **development**: `git`, `docker`, `python`, `node`, `npm`, `pip`, `poetry`, `pytest`, `make`, `cargo`, `go`, `java`, `javac`, `gcc`, `cc`
- **process**: `kill`, `pkill`, `systemctl`, `service`, `start`, `stop`, `restart`, `status`, `enable`, `disable`
- **network**: `curl`, `wget`, `nc`, `ncat`, `telnet`, `ssh`, `scp`, `ping`, `traceroute`, `dig`, `nslookup`, `host`
- **database**: `psql`, `mysql`, `sqlite3`, `mongo`, `redis-cli`, `pg_dump`
- **ai_tools**: `ollama`, `pygmentize`, `jq`, `yq`, `xmllint`, `python`

### Padrões Bloqueados

Os seguintes padrões são bloqueados por motivos de segurança:

- `rm -rf /` (deletar raiz)
- `> /dev/sd*` (sobrescrever dispositivos)
- `dd of=/dev/sd*` (dd em dispositivos)
- `mkfs` (formatar)
- `shred` (destruição segura)
- `chmod 777 /` (permissões perigosas em raiz)

### Restrições de Arquivo

- Apenas leitura
- Limitado a 10 MB de tamanho
- Paths permitidos: `/home`, `/tmp`, `/root`, `/opt`

## 🤖 Configurar Modelo Ollama para Usar Ferramentas

### Opção 1: Modelfile Customizado

Crie um arquivo `Modelfile` para o seu modelo:

```dockerfile
FROM qwen2.5-coder:7b

SYSTEM """You are an advanced AI coding assistant with access to terminal, file and system information tools.

When you need to:
- Check system status → use system_info
- Read files or configs → use read_file  
- Execute commands → use shell_exec
- List directories → use list_directory

Available tools (available at http://localhost:8503/llm-tools/*):
- shell_exec: Execute shell commands
- read_file: Read file contents
- list_directory: List directory contents
- system_info: Get system information

Always try to gather real information from the system when needed. Be proactive about checking logs, running tests, etc.
"""

PARAMETER temperature 0.7
PARAMETER num_ctx 16384
PARAMETER stop </tool_use>
PARAMETER stop [/TOOL_USE]
```

Construir:
```bash
ollama create eddie-tools -f Modelfile
```

### Opção 2: Prompt Dinâmico via API

Se usar OpenWebUI ou similar, adicione esse prompt no início:

```
You have access to execution tools. When necessary, call them using this format:

<TOOL_USE>
{
  "tool": "shell_exec",
  "params": {
    "command": "ls -la /home"
  }
}
</TOOL_USE>

Available tools:
- shell_exec: run commands
- read_file: view files
- list_directory: browse dirs
- system_info: system info
```

## 📊 Exemplo: Usar com o Copilot Localmente

### 1. Verificar Saúde

```bash
curl http://localhost:8503/llm-tools/health
```

### 2. Custom Client para Interceptar Tool Calls

Exemplo em Python:

```python
import httpx
import json
import re

async def llm_with_tools(prompt: str, model: str = "eddie-coder"):
    """Executa LLM com tool-calling capabilities."""
    
    async with httpx.AsyncClient() as client:
        # Obter ferramentas disponíveis
        tools_resp = await client.get("http://localhost:8503/llm-tools/available")
        tools = tools_resp.json()
        
        # Fazer request ao Ollama
        llm_resp = await client.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": f"{prompt}\n\nAvailable tools: {json.dumps(tools)}",
                "stream": False,
            },
            timeout=120
        )
        
        response = llm_resp.json()["response"]
        
        # Procurar por tool calls no response
        tool_calls = re.findall(r"<TOOL_USE>(.*?)</TOOL_USE>", response, re.DOTALL)
        
        for tool_call in tool_calls:
            try:
                tool_req = json.loads(tool_call)
                tool_name = tool_req.get("tool")
                params = tool_req.get("params", {})
                
                # Executar ferramenta
                exec_resp = await client.post(
                    f"http://localhost:8503/llm-tools/execute",
                    json={
                        "tool_name": tool_name,
                        "params": params
                    }
                )
                
                result = exec_resp.json()
                print(f"\n[Tool: {tool_name}]\n{json.dumps(result, indent=2)}")
            
            except Exception as e:
                print(f"Erro ao executar tool: {e}")
        
        return response
```

## 🚀 Integração com OpenWebUI

Se estiver rodando OpenWebUI, você pode registrar essas ferramentas como **Tools** da plataforma:

1. Acesse: `http://localhost:3000/admin/functions`
2. Crie uma função "Shell Executor":

```python
def shell_executor(command: str, timeout: int = 30) -> dict:
    import httpx
    client = httpx.Client()
    result = client.post(
        "http://localhost:8503/llm-tools/exec-shell",
        json={"command": command, "timeout": timeout}
    ).json()
    return result
```

3. Configure no modelo para usar essa função

## 📋 Health Check

```bash
curl http://localhost:8503/llm-tools/health
```

Resposta:
```json
{
  "status": "healthy",
  "executor": "online",
  "timestamp": "2026-03-01T16:30:00.000000"
}
```

## 🔧 Troubleshooting

### Tool não aparece em `/available`

```bash
curl http://localhost:8503/llm-tools/available -v
```

Se retornar 404, a rota não foi registrada. Verifique a API startup logs.

### Comando bloqueado

Verifique se o comando está na whitelist. Use um comando alternativo autorizado.

### Timeout

Aumente o `timeout` nos parâmetros (máximo 300s).

### Permissões negadas

Verifique as permissões do arquivo/diretório com o user que roda a API.

## 📚 Referência de API

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/llm-tools/available` | GET | Lista todas as ferramentas |
| `/llm-tools/execute` | POST | Executa qualquer ferramenta |
| `/llm-tools/exec-shell` | POST | Atalho para shell_exec |
| `/llm-tools/read-file` | POST | Atalho para read_file |
| `/llm-tools/list-directory` | POST | Atalho para list_directory |
| `/llm-tools/system-info` | GET | Atalho para system_info |
| `/llm-tools/health` | GET | Health check |
| `/llm-tools/openwebui-schema` | GET | Schema para OpenWebUI |

## 🎓 Casos de Uso

### Debugging Automático

```bash
# LLM analisa erro e executa comando de debug
curl -X POST http://localhost:8503/llm-tools/exec-shell \
  -d '{"command": "docker logs my-service | tail -50"}'
```

### Code Analysis

```bash
# LLM lê arquivo e analisa
curl -X POST http://localhost:8503/llm-tools/read-file \
  -d '{"filepath": "/home/user/my_app.py", "max_lines": 100}'
```

### System Monitoring

```bash
# LLM obtém estado do sistema
curl http://localhost:8503/llm-tools/system-info
```

## ⚠️ Notas Importantes

1. **Segurança**: Essas ferramentas devem rodar apenas em rede de confiança ou com autenticação
2. **Limite de Recursos**: Defina `cgroup` limits se usar em produção
3. **Audit**: Todos os comandos são logados em `logs/llm-tools.log`
4. **Sandboxing**: Considere usar containers ou VMs para isolamento

## 🤝 Contribuições

Para adicionar novas ferramentas, edite `llm_tool_executor.py` e registre em `get_available_tools()`.
