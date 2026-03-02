"""
Rotas FastAPI para o LLM Tool Executor Enhanced.

Endpoints que permitem ao LLM invocar ferramentas de terminal,
arquivo e sistema similar ao function calling do GitHub Copilot.
Integra AgentMemory (reforço de aprendizado) + AgentCommunicationBus.

Endpoints:
    GET  /llm-tools/available       - Lista ferramentas disponíveis
    POST /llm-tools/execute         - Executa ferramenta com aprendizado
    POST /llm-tools/exec-shell      - Atalho para shell_exec
    POST /llm-tools/read-file       - Atalho para read_file
    POST /llm-tools/list-directory  - Atalho para list_directory
    GET  /llm-tools/system-info     - Atalho para system_info
    GET  /llm-tools/system-prompt   - System prompt para Ollama
    GET  /llm-tools/learning-stats  - Estatísticas de aprendizado
    GET  /llm-tools/openwebui-schema
    GET  /llm-tools/health
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import json

from specialized_agents.llm_tool_executor import get_llm_tool_executor
from specialized_agents.llm_tool_executor_enhanced import get_enhanced_executor
from specialized_agents.llm_tool_prompts import (
    get_tool_system_prompt,
    parse_tool_calls,
    get_tool_result_prompt,
    strip_tool_calls,
)
from specialized_agents.llm_tool_schemas import (
    get_ollama_tools,
    get_tool_system_message,
    normalize_tool_calls,
    format_tool_result_message,
    format_assistant_tool_call_message,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm-tools", tags=["llm-tools"])


# ─────────────────────────────────────────────────────────────────────────°
# Modelos Pydantic
# ─────────────────────────────────────────────────────────────────────────°

class ExecuteToolRequest(BaseModel):
    """Requisição para executar ferramenta."""
    tool_name: str = Field(..., description="Nome da ferramenta", example="shell_exec")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parâmetros da ferramenta")


class ShellExecRequest(BaseModel):
    """Requisição de execução shell."""
    command: str = Field(..., description="Comando a executar", example="ls -la /home")
    timeout: int = Field(30, description="Timeout em segundos", ge=1, le=300)
    cwd: Optional[str] = Field(None, description="Diretório de trabalho")


class ReadFileRequest(BaseModel):
    """Requisição de leitura de arquivo."""
    filepath: str = Field(..., description="Caminho do arquivo", example="/etc/hostname")
    max_lines: Optional[int] = Field(None, description="Máximo de linhas")


class ListDirRequest(BaseModel):
    """Requisição de listagem de diretório."""
    dirpath: str = Field(..., description="Caminho do diretório", example="/home")
    recursive: bool = Field(False, description="Listar recursivamente")


# ─────────────────────────────────────────────────────────────────────────°
# Endpoints
# ─────────────────────────────────────────────────────────────────────────°

@router.get("/available", summary="Listar ferramentas disponíveis")
async def list_available_tools():
    """Retorna lista de ferramentas disponíveis para o LLM invocar."""
    executor = get_llm_tool_executor()
    return executor.get_available_tools()


@router.post("/execute", summary="Executar ferramenta com aprendizado")
async def execute_tool(req: ExecuteToolRequest):
    """Executa uma ferramenta com registro de decisão e reforço de aprendizado."""
    enhanced = get_enhanced_executor()

    logger.info(f"Executando ferramenta (enhanced): {req.tool_name}")
    result = await enhanced.execute_with_learning(
        tool_name=req.tool_name,
        params=req.params,
        user_query=req.params.get("_user_query", ""),
        conversation_id=req.params.get("_conversation_id", ""),
    )

    if not result.get("success", False):
        logger.warning(f"Ferramenta falhou: {req.tool_name} - {result.get('error')}")

    return result


@router.post("/exec-shell", summary="Executar comando shell")
async def exec_shell(req: ShellExecRequest):
    """Atalho para executar comando shell com aprendizado."""
    enhanced = get_enhanced_executor()

    logger.info(f"Shell exec (enhanced): {req.command[:100]}")
    result = await enhanced.execute_with_learning(
        tool_name="shell_exec",
        params={
            "command": req.command,
            "timeout": req.timeout,
            "cwd": req.cwd,
        },
    )

    return result


@router.post("/read-file", summary="Ler arquivo")
async def read_file_endpoint(req: ReadFileRequest):
    """Atalho para ler arquivo com aprendizado."""
    enhanced = get_enhanced_executor()

    logger.info(f"Leitura de arquivo (enhanced): {req.filepath}")
    result = await enhanced.execute_with_learning(
        tool_name="read_file",
        params={
            "filepath": req.filepath,
            "max_lines": req.max_lines,
        },
    )

    return result


@router.post("/list-directory", summary="Listar diretório")
async def list_directory_endpoint(req: ListDirRequest):
    """Atalho para listar diretório com aprendizado."""
    enhanced = get_enhanced_executor()

    logger.info(f"Listagem de diretório (enhanced): {req.dirpath}")
    result = await enhanced.execute_with_learning(
        tool_name="list_directory",
        params={
            "dirpath": req.dirpath,
            "recursive": req.recursive,
        },
    )

    return result


@router.get("/system-info", summary="Obter informações do sistema")
async def get_system_info():
    """Retorna informações do sistema."""
    executor = get_llm_tool_executor()
    
    logger.info("Solicitação de info do sistema")
    result = await executor.get_system_info()
    
    return result


# ─────────────────────────────────────────────────────────────────────────°
# System Prompt + Learning Stats
# ─────────────────────────────────────────────────────────────────────────°

@router.get("/system-prompt", summary="System prompt para Ollama")
async def get_system_prompt(extra_context: str = ""):
    """
    Retorna system prompt que instrui o modelo Ollama a usar ferramentas.
    Enviar como role=system no /api/chat.
    """
    prompt = get_tool_system_prompt(extra_context=extra_context)
    return {
        "system_prompt": prompt,
        "format": "tool_call",
        "tag_open": "<tool_call>",
        "tag_close": "</tool_call>",
    }


@router.get("/learning-stats", summary="Estatísticas de aprendizado")
async def learning_stats():
    """Retorna estatísticas de aprendizado do executor."""
    enhanced = get_enhanced_executor()
    stats = await enhanced.get_learning_stats()
    return stats


# ─────────────────────────────────────────────────────────────────────────°
# Ollama Native Tool Calling Schema
# ─────────────────────────────────────────────────────────────────────────°

@router.get("/ollama-tools-schema", summary="Schema nativo Ollama tools")
async def ollama_tools_schema():
    """
    Retorna ferramentas no formato nativo Ollama /api/chat `tools`.
    
    Usar diretamente como valor do campo `tools` no payload do /api/chat.
    Compatível com qualquer modelo que suporte tool calling (qwen3, llama3.1+, etc).
    
    Exemplo de uso:
    ```python
    import httpx
    schema = httpx.get("http://localhost:8503/llm-tools/ollama-tools-schema").json()
    payload = {
        "model": "qwen3:8b",
        "messages": [{"role": "user", "content": "verifique o docker"}],
        "tools": schema["tools"],
        "stream": False,
    }
    resp = httpx.post("http://ollama:11434/api/chat", json=payload)
    ```
    """
    return {
        "tools": get_ollama_tools(),
        "system_message": get_tool_system_message(),
        "format": "ollama_native",
        "supported_models": [
            "qwen3:8b", "qwen3:4b", "qwen3:14b", "qwen3:30b",
            "qwen2.5-coder:7b", "qwen2.5:7b",
            "llama3.1:8b", "llama3.2",
            "mistral-nemo", "command-r-plus",
        ],
    }


# ─────────────────────────────────────────────────────────────────────────°
# Chat endpoint com loop agentic (tool calling nativo)
# ─────────────────────────────────────────────────────────────────────────°

class ChatRequest(BaseModel):
    """Requisição de chat com tool calling automático."""
    prompt: str = Field(..., description="Pergunta do usuário")
    model: str = Field("qwen3:8b", description="Modelo Ollama")
    ollama_host: str = Field(
        "http://192.168.15.2:11434",
        description="Host Ollama (default GPU0)",
    )
    max_rounds: int = Field(5, description="Máximo de rounds de tool calling", ge=1, le=10)
    use_native_tools: bool = Field(True, description="Usar tool calling nativo (True) ou tags <tool_call> (False)")
    conversation_id: Optional[str] = Field(None, description="ID da conversa para tracking")


@router.post("/chat", summary="Chat com tool calling automático")
async def chat_with_tools(req: ChatRequest):
    """
    Endpoint agentic: envia prompt ao Ollama, intercepta tool_calls,
    executa automaticamente, re-injeta resultados, retorna resposta final.

    Suporta dois modos:
    - use_native_tools=True: usa `tools` nativo do Ollama (recomendado)
    - use_native_tools=False: usa tags <tool_call> (legado, para modelos sem suporte)

    Fluxo:
    1. Envia prompt + tools ao Ollama
    2. Se resposta contém tool_calls → executa via executor enhanced
    3. Adiciona resultado como role=tool no histórico
    4. Re-envia ao Ollama para interpretação
    5. Repete até sem tool_calls ou max_rounds
    6. Retorna resposta final + metadata de execuções
    """
    import httpx

    enhanced = get_enhanced_executor()
    messages = [
        {"role": "system", "content": get_tool_system_message()},
        {"role": "user", "content": req.prompt},
    ]
    executions = []
    final_response = ""

    for round_num in range(req.max_rounds):
        # Montar payload
        payload = {
            "model": req.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 2048},
        }
        if req.use_native_tools:
            payload["tools"] = get_ollama_tools()

        # Chamar Ollama
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{req.ollama_host.rstrip('/')}/api/chat",
                    json=payload,
                )
                if resp.status_code != 200:
                    raise HTTPException(502, f"Ollama retornou {resp.status_code}")
                data = resp.json()
        except httpx.TimeoutException:
            raise HTTPException(504, "Ollama timeout (120s)")
        except httpx.ConnectError:
            raise HTTPException(502, f"Não foi possível conectar ao Ollama em {req.ollama_host}")

        message = data.get("message", {})
        content = message.get("content", "")
        native_tool_calls = message.get("tool_calls", [])

        # ── Modo nativo: verificar tool_calls na resposta ──
        if req.use_native_tools and native_tool_calls:
            # Adicionar mensagem do assistente com tool_calls ao histórico
            messages.append(format_assistant_tool_call_message(native_tool_calls))

            # Executar cada tool call
            normalized = normalize_tool_calls(native_tool_calls)
            for call in normalized:
                tool_name = call["tool"]
                params = call["params"]

                result = await enhanced.execute_with_learning(
                    tool_name=tool_name,
                    params=params,
                    user_query=req.prompt,
                    conversation_id=req.conversation_id,
                )

                executions.append({
                    "round": round_num + 1,
                    "tool": tool_name,
                    "params": params,
                    "success": result.get("success", False),
                    "learning": result.get("_learning"),
                })

                # Adicionar resultado como role=tool
                tool_msg = format_tool_result_message(tool_name, result)
                messages.append(tool_msg)

            continue  # próximo round para LLM interpretar resultados

        # ── Modo legado: verificar tags <tool_call> ──
        if not req.use_native_tools and content:
            tag_calls = parse_tool_calls(content)
            if tag_calls:
                messages.append({"role": "assistant", "content": content})

                for call in tag_calls:
                    tool_name = call.get("tool", "unknown")
                    params = call.get("params", {})

                    result = await enhanced.execute_with_learning(
                        tool_name=tool_name,
                        params=params,
                        user_query=req.prompt,
                        conversation_id=req.conversation_id,
                    )

                    executions.append({
                        "round": round_num + 1,
                        "tool": tool_name,
                        "params": params,
                        "success": result.get("success", False),
                        "learning": result.get("_learning"),
                    })

                    formatted = get_tool_result_prompt(tool_name, result)
                    messages.append({"role": "user", "content": formatted})

                continue  # próximo round

        # Sem tool calls — resposta final
        final_response = content
        break
    else:
        # Atingiu max_rounds
        final_response = content + "\n\n⚠️ Limite de rounds de ferramentas atingido."

    return {
        "response": final_response,
        "model": req.model,
        "rounds": len(executions),
        "executions": executions,
        "conversation_id": req.conversation_id,
        "mode": "native" if req.use_native_tools else "legacy_tags",
    }


# ─────────────────────────────────────────────────────────────────────────°
# Integração com OpenWebUI / Ollama - Tool Calling
# ─────────────────────────────────────────────────────────────────────────°

@router.get("/openwebui-schema", summary="Schema para OpenWebUI Tool Integration")
async def openwebui_tool_schema():
    """
    Retorna schema no formato esperado pelo OpenWebUI para integração de ferramentas.
    
    Permite que o modelo OpenWebUI invoque essas ferramentas automaticamente
    como part do response generation.
    """
    executor = get_llm_tool_executor()
    tools = executor.get_available_tools()
    
    return {
        "tools": [
            {
                "id": "shell-executor",
                "name": "Shell Command Executor",
                "description": "Execute shell commands on the system",
                "type": "function",
                "spec": {
                    "name": "shell_exec",
                    "description": "Execute system shell commands",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Command to execute"
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Timeout in seconds",
                                "default": 30
                            },
                            "cwd": {
                                "type": "string",
                                "description": "Working directory"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "id": "file-reader",
                "name": "File Reader",
                "description": "Read file contents",
                "type": "function",
                "spec": {
                    "name": "read_file",
                    "description": "Read file contents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "File path to read"
                            },
                            "max_lines": {
                                "type": "integer",
                                "description": "Maximum lines to read"
                            }
                        },
                        "required": ["filepath"]
                    }
                }
            }
        ]
    }


# ─────────────────────────────────────────────────────────────────────────°
# Health check
# ─────────────────────────────────────────────────────────────────────────°

@router.get("/health", summary="Health check")
async def health_check():
    """Verifica saúde do executor."""
    try:
        executor = get_llm_tool_executor()
        info = await executor.get_system_info()
        if info.get("success"):
            return {
                "status": "healthy",
                "executor": "online",
                "timestamp": info.get("timestamp"),
            }
    except Exception as e:
        logger.error(f"Health check falhou: {e}")
    
    return {
        "status": "unhealthy",
        "executor": "offline",
        "error": "Falha ao obter info do sistema",
    }
