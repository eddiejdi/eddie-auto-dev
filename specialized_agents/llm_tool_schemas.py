"""
LLM Tool Schemas — Definições de ferramentas no formato nativo Ollama.

Fornece schemas compatíveis com o parâmetro `tools` do endpoint /api/chat
do Ollama, seguindo o padrão OpenAI Function Calling.

Ollama aceita:
    {
        "type": "function",
        "function": {
            "name": "...",
            "description": "...",
            "parameters": { JSON Schema }
        }
    }

O modelo retorna:
    message.tool_calls: [
        {"function": {"name": "...", "arguments": {...}}}
    ]

Uso:
    from specialized_agents.llm_tool_schemas import (
        get_ollama_tools,
        get_tool_system_message,
        normalize_tool_call,
    )

    # Injetar no /api/chat
    payload = {
        "model": "qwen3:8b",
        "messages": [...],
        "tools": get_ollama_tools(),
        "stream": False,
    }

Referência:
    - https://github.com/ollama/ollama/blob/main/docs/api.md#chat-request-with-tools
    - https://ollama.com/blog/tool-support
"""

from typing import Dict, Any, List, Optional

# ──────────────────────────────────────────────────────────────────────────
# Definição das ferramentas (formato JSON Schema / OpenAI Function Calling)
# ──────────────────────────────────────────────────────────────────────────

TOOL_SHELL_EXEC = {
    "type": "function",
    "function": {
        "name": "shell_exec",
        "description": (
            "Execute a shell command on the system. "
            "Allowed: git, docker, systemctl, journalctl, ps, df, free, ls, cat, head, tail, "
            "grep, find, wc, echo, curl, ping, psql, pip, python, pytest, ollama, etc. "
            "Blocked: rm -rf /, dd of=/dev, mkfs, shred, chmod 777 /."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30, max: 300)",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
            },
            "required": ["command"],
        },
    },
}

TOOL_READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "Read the contents of a file. Allowed paths: /home, /tmp, /opt, /etc, /var/log. "
            "Use max_lines to limit output for large files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Absolute path of the file to read",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (optional)",
                },
            },
            "required": ["filepath"],
        },
    },
}

TOOL_LIST_DIRECTORY = {
    "type": "function",
    "function": {
        "name": "list_directory",
        "description": (
            "List files and directories in a given path. "
            "Returns name, size, type, and modification date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dirpath": {
                    "type": "string",
                    "description": "Directory path to list",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List recursively (default: false, max depth 2)",
                },
            },
            "required": ["dirpath"],
        },
    },
}

TOOL_SYSTEM_INFO = {
    "type": "function",
    "function": {
        "name": "system_info",
        "description": (
            "Get system information including hostname, OS, CPU count, "
            "memory usage (total/available/percent), disk usage, "
            "uptime, and current load averages."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


# ──────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────

def get_ollama_tools() -> List[Dict[str, Any]]:
    """
    Retorna lista de ferramentas no formato nativo Ollama /api/chat.

    Uso:
        payload["tools"] = get_ollama_tools()

    Returns:
        Lista de tool definitions para o campo `tools` do /api/chat.
    """
    return [
        TOOL_SHELL_EXEC,
        TOOL_READ_FILE,
        TOOL_LIST_DIRECTORY,
        TOOL_SYSTEM_INFO,
    ]


def get_tool_names() -> List[str]:
    """Retorna nomes de todas as ferramentas disponíveis."""
    return [t["function"]["name"] for t in get_ollama_tools()]


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Busca definição de ferramenta pelo nome."""
    for tool in get_ollama_tools():
        if tool["function"]["name"] == name:
            return tool
    return None


def get_tool_system_message() -> str:
    """
    Retorna mensagem de sistema para uso com tool calling nativo do Ollama.

    Diferente do system prompt com tags <tool_call> (llm_tool_prompts.py),
    este prompt é complementar — o Ollama injeta automaticamente as definições
    de ferramentas no contexto quando `tools` é fornecido no request.
    Este prompt reforça o comportamento de execução automática.

    Returns:
        String para usar como system message no /api/chat.
    """
    return """Você é um assistente técnico especializado no homelab Shared Auto-Dev.

## REGRAS DE COMPORTAMENTO

1. Quando o usuário pedir para verificar, executar, consultar ou checar algo:
   - Use as ferramentas disponíveis AUTOMATICAMENTE
   - NUNCA retorne instruções manuais (curl, comandos para o usuário)
   - Execute VOCÊ MESMO usando as tools

2. Após executar uma ferramenta e receber o resultado:
   - Analise o resultado
   - Responda em linguagem natural, clara e objetiva
   - Destaque problemas ou alertas encontrados

3. Você pode chamar múltiplas ferramentas para uma resposta completa:
   - Ex: verificar status do docker E logs do container

4. Se o comando for bloqueado pela segurança, informe ao usuário sem tentar contornar.

## CONTEXTO DO SISTEMA

- Homelab com dual-GPU (RTX 2060 + GTX 1050)
- Ollama em :11434 (GPU0) e :11435 (GPU1)
- Trading agents (BTC, ETH, XRP, SOL, DOGE, ADA) em containers Docker
- API especializada em :8503
- PostgreSQL em :5433, database postgres, schema btc
- Grafana em :3000, Prometheus em :9090
"""


def normalize_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza um tool_call do Ollama para o formato interno do executor.

    Ollama retorna:
        {"function": {"name": "shell_exec", "arguments": {"command": "ls"}}}

    Executor espera:
        {"tool": "shell_exec", "params": {"command": "ls"}}

    Args:
        tool_call: Dict do Ollama (message.tool_calls[i])

    Returns:
        Dict normalizado {tool, params}
    """
    func = tool_call.get("function", {})
    arguments = func.get("arguments", {})
    # Se arguments veio como string JSON, parsear
    if isinstance(arguments, str):
        try:
            import json
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, ValueError):
            arguments = {"raw": arguments}
    return {
        "tool": func.get("name", ""),
        "params": arguments,
    }


def normalize_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normaliza lista de tool_calls do Ollama para formato interno.

    Args:
        tool_calls: Lista do Ollama message.tool_calls

    Returns:
        Lista normalizada [{tool, params}, ...]
    """
    if not tool_calls:
        return []
    return [normalize_tool_call(tc) for tc in tool_calls]


def format_tool_result_message(
    tool_name: str,
    result: Dict[str, Any],
    max_output: int = 4000,
) -> Dict[str, str]:
    """
    Formata resultado de execução como mensagem role=tool para o Ollama.

    Formato nativo Ollama:
        {"role": "tool", "content": "resultado", "tool_name": "shell_exec"}

    Args:
        tool_name: Nome da ferramenta executada
        result: Resultado do executor
        max_output: Máximo de chars no output (trunca se necessário)

    Returns:
        Dict pronto para adicionar ao array messages[]
    """
    if result.get("success"):
        output = result.get("stdout", result.get("content", ""))
        if len(output) > max_output:
            output = output[:max_output] + f"\n... (truncado, {len(output)} chars total)"
        content = output or "(nenhuma saída)"
    else:
        error = result.get("stderr", result.get("error", "Erro desconhecido"))
        exit_code = result.get("exit_code", -1)
        content = f"ERRO (exit {exit_code}): {error}"

    return {
        "role": "tool",
        "content": content,
        "tool_name": tool_name,
    }


def format_assistant_tool_call_message(
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Formata a mensagem do assistente com tool_calls para o histórico.

    Usada para manter o histórico correto no loop agentic:
    user → assistant (com tool_calls) → tool (resultado) → assistant (resposta)

    Args:
        tool_calls: Lista de tool_calls como retornada pelo Ollama

    Returns:
        Dict pronto para adicionar ao array messages[]
    """
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": tool_calls,
    }
