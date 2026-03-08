"""
Proxy Tool Interceptor — Intercepta requests /api/chat no LLM Optimizer Proxy
e injeta tool calling nativo do Ollama automaticamente.

DEPLOYMENT:
    Este módulo deve ser integrado ao llm-optimizer no homelab (porta 8512).
    Pode ser usado como:
    1. Middleware FastAPI no proxy existente
    2. Módulo standalone importado pelo proxy

    # No llm_optimizer_v2.3.py, adicionar:
    from proxy_tool_interceptor import ToolInterceptor
    interceptor = ToolInterceptor(executor_url="http://localhost:8503")

    @app.post("/api/chat")
    async def chat_handler(request: Request):
        body = await request.json()
        body = interceptor.inject_tools(body)
        # ... forward to Ollama ...
        response = await forward_to_ollama(body)
        if interceptor.has_tool_calls(response):
            return await interceptor.handle_tool_loop(body, response)
        return response

COMO FUNCIONA:
    1. Client envia POST /api/chat ao proxy (LLM Optimizer :8512)
    2. Interceptor detecta se request NÃO tem `tools` definidas
    3. Injeta tools nativas + system message do Shared
    4. Forward pra Ollama com tools
    5. Ollama retorna tool_calls no response
    6. Interceptor executa tools via API :8503
    7. Re-envia resultado ao Ollama para interpretação
    8. Retorna resposta final ao client (transparente)

    ┌─────────┐    ┌─────────────┐    ┌─────────┐    ┌─────────────┐
    │  Client │───▶│  Proxy:8512 │───▶│ Ollama  │    │ Shared API   │
    │  (Cline)│    │ Interceptor │◀───│ :11434  │    │   :8503     │
    └─────────┘    │             │───▶│         │    │ /llm-tools/ │
                   │             │◀───│         │    │             │
                   │             │────────────────▶│             │
                   │             │◀───────────────│             │
                   └─────────────┘                  └─────────────┘

REFERÊNCIA:
    - Ollama API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
    - specialized_agents/llm_tool_schemas.py (schemas)
    - specialized_agents/llm_tools_api.py (API endpoints)
"""

import os
import json
import time
import copy
import logging
from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    httpx = None
    HAS_HTTPX = False

logger = logging.getLogger("proxy_tool_interceptor")

# ── Configuração ──
EDDIE_API_URL = os.getenv("EDDIE_API_URL", "http://localhost:8503")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
MAX_TOOL_ROUNDS = int(os.getenv("TOOL_MAX_ROUNDS", "10"))
TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", "60"))

# Modelos que suportam tool calling nativo
TOOL_CAPABLE_MODELS = {
    "qwen3", "qwen2.5", "qwen2.5-coder", "qwen2.5-coder:7b",
    "qwen3:8b", "qwen3:1.7b", "qwen3:0.6b", "qwen3:4b",
    "llama3.1", "llama3.2", "llama3.3", "llama4",
    "mistral", "mistral-nemo", "mistral-small",
    "command-r", "command-r-plus",
    "granite3-dense", "granite3-moe",
    "shared-coder", "shared-tools",
    # base names (sem tags)
}

# ══════════════════════════════════════════════════════════════════════════
# Tool Definitions (formato nativo Ollama)
# ══════════════════════════════════════════════════════════════════════════

NATIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": (
                "Execute a shell command on the homelab system. "
                "Supports: docker, systemctl, git, find, grep, cat, ls, df, free, "
                "ps, journalctl, echo, touch, tee, sort, uniq, cut, awk, sed, "
                "pip, python3, node, npm, go, cargo, dotnet, php, javac, java. "
                "Blocked: rm -rf /, dd of=/dev, mkfs, shred, chmod 777 /"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 30, max 300)"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (optional)"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read contents of a file. Allowed paths: /home, /tmp, /opt, /etc, /var/log. "
                "Use max_lines to limit output for large files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Absolute file path to read"
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Max lines to read (optional)"
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories with size, type and modification date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dirpath": {
                        "type": "string",
                        "description": "Directory path to list"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Recurse subdirectories (max depth 2)"
                    }
                },
                "required": ["dirpath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get system info: hostname, OS, CPU, RAM, disk, uptime, load averages.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

TOOL_SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are Shared, an AI assistant with tool execution capabilities. "
        "You can execute shell commands, read files, list directories, and get system info "
        "on the homelab server. When the user asks about system status, Docker, "
        "logs, files, or any operational task, USE the appropriate tool. "
        "Analyze tool results and provide clear, useful summaries."
    )
}


def _is_tool_capable(model: str) -> bool:
    """Verifica se o modelo suporta tool calling nativo."""
    if not model:
        return False
    model_lower = model.lower().strip()
    # Verifica match exato e prefixo
    for m in TOOL_CAPABLE_MODELS:
        if model_lower == m or model_lower.startswith(f"{m}:") or model_lower.startswith(f"{m}-"):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════
# ToolInterceptor — Classe principal
# ══════════════════════════════════════════════════════════════════════════

class ToolInterceptor:
    """
    Intercepta requests /api/chat e gerencia o loop de tool calling.
    
    Usage:
        interceptor = ToolInterceptor(executor_url="http://localhost:8503")
        
        # Em cada request:
        body = interceptor.inject_tools(body)
        response = await forward_to_ollama(body)
        if interceptor.has_tool_calls(response):
            final_response = await interceptor.handle_tool_loop(body, response)
    """

    def __init__(
        self,
        executor_url: str = EDDIE_API_URL,
        ollama_host: str = OLLAMA_HOST,
        max_rounds: int = MAX_TOOL_ROUNDS,
        tool_timeout: int = TOOL_TIMEOUT,
    ):
        self.executor_url = executor_url.rstrip("/")
        self.ollama_host = ollama_host.rstrip("/")
        self.max_rounds = max_rounds
        self.tool_timeout = tool_timeout
        self.stats = {
            "requests_intercepted": 0,
            "tools_injected": 0,
            "tool_calls_executed": 0,
            "tool_loops_completed": 0,
            "errors": 0,
        }

    def inject_tools(self, body: dict) -> dict:
        """
        Injeta tools nativas + system message se o request não tem tools.
        Retorna body modificado (NÃO muta o original).
        """
        # Já tem tools? Não injeta
        if body.get("tools"):
            return body

        # Modelo suporta tools?
        model = body.get("model", "")
        if not _is_tool_capable(model):
            logger.debug(f"Modelo '{model}' não suporta tools, skipping injection")
            return body

        # Stream não é suportado com tool calling de forma simples
        if body.get("stream", False):
            logger.debug("Stream mode, desabilitando para tool calling")

        modified = copy.deepcopy(body)
        modified["tools"] = NATIVE_TOOLS
        modified["stream"] = False  # Tool calling requer non-streaming

        # Injeta system message se não houver
        messages = modified.get("messages", [])
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            messages.insert(0, TOOL_SYSTEM_MESSAGE)
            modified["messages"] = messages

        self.stats["tools_injected"] += 1
        self.stats["requests_intercepted"] += 1
        logger.info(f"[TOOL-INTERCEPT] Tools injetadas para modelo '{model}'")
        return modified

    def has_tool_calls(self, response: dict) -> bool:
        """Verifica se o response do Ollama contém tool_calls."""
        msg = response.get("message", {})
        tool_calls = msg.get("tool_calls")
        return bool(tool_calls)

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Executa uma tool via API do Shared (:8503)."""
        if not HAS_HTTPX:
            return {"success": False, "error": "httpx not available"}

        url = f"{self.executor_url}/llm-tools/execute"
        payload = {
            "tool_name": tool_name,
            "params": arguments,
        }

        try:
            async with httpx.AsyncClient(timeout=self.tool_timeout) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    self.stats["tool_calls_executed"] += 1
                    return result
                else:
                    return {
                        "success": False,
                        "error": f"API returned {resp.status_code}: {resp.text[:500]}"
                    }
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"[TOOL-INTERCEPT] Erro executando {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    def _format_tool_result(self, tool_name: str, result: dict) -> str:
        """Formata resultado da tool para inclusão na conversa."""
        if result.get("success"):
            # Extrai conteúdo relevante
            content = (
                result.get("stdout") or
                result.get("content") or
                result.get("output") or
                json.dumps(result, ensure_ascii=False, indent=2)
            )
            return str(content)[:8000]
        else:
            error = result.get("stderr") or result.get("error") or "Unknown error"
            return f"ERRO: {error}"

    async def _call_ollama(self, body: dict) -> dict:
        """Chama Ollama com o body atual."""
        if not HAS_HTTPX:
            return {"message": {"content": "httpx not available", "role": "assistant"}}

        url = f"{self.ollama_host}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"[TOOL-INTERCEPT] Erro chamando Ollama: {e}")
            return {"message": {"content": f"Erro: {e}", "role": "assistant"}}

    async def handle_tool_loop(
        self,
        body: dict,
        initial_response: dict,
    ) -> dict:
        """
        Executa o loop completo de tool calling:
        1. Extrai tool_calls do response
        2. Executa cada tool via API :8503
        3. Adiciona resultados como mensagens role=tool
        4. Re-chama Ollama com contexto atualizado
        5. Repete até não ter mais tool_calls (ou atingir max_rounds)
        
        Retorna o response final do Ollama (com a resposta interpretada).
        """
        current_body = copy.deepcopy(body)
        current_response = initial_response
        messages = current_body.get("messages", [])

        for round_num in range(self.max_rounds):
            msg = current_response.get("message", {})
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                # Sem mais tool_calls — resposta final
                break

            logger.info(
                f"[TOOL-INTERCEPT] Round {round_num + 1}: "
                f"{len(tool_calls)} tool_calls a executar"
            )

            # Adiciona a mensagem do assistente (com tool_calls) ao histórico
            messages.append({
                "role": "assistant",
                "content": msg.get("content", ""),
                "tool_calls": tool_calls,
            })

            # Executa cada tool_call
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                arguments = func.get("arguments", {})

                # Se arguments veio como string JSON, parse
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {"raw": arguments}

                logger.info(f"[TOOL-INTERCEPT] Executando: {tool_name}({arguments})")
                result = await self.execute_tool(tool_name, arguments)
                result_text = self._format_tool_result(tool_name, result)

                # Adiciona resultado como mensagem role=tool
                messages.append({
                    "role": "tool",
                    "content": result_text,
                })

            # Re-chama Ollama com o histórico atualizado
            current_body["messages"] = messages
            current_response = await self._call_ollama(current_body)

        self.stats["tool_loops_completed"] += 1
        return current_response

    def get_stats(self) -> dict:
        """Retorna estatísticas de uso do interceptor."""
        return dict(self.stats)


# ══════════════════════════════════════════════════════════════════════════
# FastAPI Middleware (para integrar diretamente no proxy)
# ══════════════════════════════════════════════════════════════════════════

def create_tool_middleware(app, interceptor: Optional[ToolInterceptor] = None):
    """
    Cria um middleware FastAPI que intercepta /api/chat.

    Uso no proxy existente:
        from proxy_tool_interceptor import ToolInterceptor, create_tool_middleware
        interceptor = ToolInterceptor()
        create_tool_middleware(app, interceptor)

    Ou como alternativa, registrar as rotas manualmente:
        from proxy_tool_interceptor import ToolInterceptor
        interceptor = ToolInterceptor()

        @app.post("/api/chat")  
        async def chat_with_tools(request: Request):
            body = await request.json()
            body = interceptor.inject_tools(body)
            response = await forward_to_ollama(body)
            if interceptor.has_tool_calls(response):
                response = await interceptor.handle_tool_loop(body, response)
            return response
    """
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        import asyncio
    except ImportError:
        logger.warning("starlette não disponível, middleware não criado")
        return

    if interceptor is None:
        interceptor = ToolInterceptor()

    class ToolMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Só intercepta POST /api/chat
            if request.method == "POST" and request.url.path == "/api/chat":
                try:
                    body = await request.json()

                    # Injetar tools se aplicável
                    modified_body = interceptor.inject_tools(body)

                    # Se tools foram injetadas, gerenciar o loop
                    if modified_body.get("tools") and not body.get("tools"):
                        # Chamar Ollama com tools
                        response = await interceptor._call_ollama(modified_body)

                        # Se tem tool_calls, executar o loop
                        if interceptor.has_tool_calls(response):
                            response = await interceptor.handle_tool_loop(
                                modified_body, response
                            )

                        return JSONResponse(content=response)

                except Exception as e:
                    logger.error(f"[TOOL-MIDDLEWARE] Erro: {e}")
                    # Fallback: deixa passar sem interceptar

            return await call_next(request)

    app.add_middleware(ToolMiddleware)
    logger.info("[TOOL-MIDDLEWARE] Middleware de tool calling registrado em /api/chat")

    # Endpoint de stats
    from fastapi import APIRouter
    router = APIRouter(prefix="/tool-interceptor", tags=["tool-interceptor"])

    @router.get("/stats")
    async def tool_stats():
        return interceptor.get_stats()

    @router.get("/tools")
    async def list_tools():
        return {"tools": NATIVE_TOOLS, "count": len(NATIVE_TOOLS)}

    app.include_router(router)


# ══════════════════════════════════════════════════════════════════════════
# Deploy helper — gera snippet para integrar no proxy
# ══════════════════════════════════════════════════════════════════════════

DEPLOY_SNIPPET = '''
# ─── Adicionar ao llm_optimizer_v2.3.py (ou equivalente) ───

# No topo do arquivo, adicionar:
from proxy_tool_interceptor import ToolInterceptor, create_tool_middleware, NATIVE_TOOLS

# Após criar o app FastAPI:
tool_interceptor = ToolInterceptor(
    executor_url="http://localhost:8503",  # Shared API
    ollama_host="http://127.0.0.1:11434",  # Ollama local no homelab
    max_rounds=10,
)

# OPÇÃO A: Middleware automático (intercepts /api/chat transparently)
create_tool_middleware(app, tool_interceptor)

# OPÇÃO B: Manual (maior controle, recomendado)
# Na função de forward existente (ex: handle_chat_request):
async def enhanced_chat_handler(body: dict) -> dict:
    """Handler com tool calling integrado."""
    # 1. Injetar tools se necessário
    body = tool_interceptor.inject_tools(body)
    
    # 2. Forward para Ollama
    response = await forward_to_ollama(body)  # Sua função existente
    
    # 3. Se tem tool_calls, executar loop
    if tool_interceptor.has_tool_calls(response):
        response = await tool_interceptor.handle_tool_loop(body, response)
    
    return response

# ─── Prometheus metrics (opcional) ───
# Nos seus STATS existentes, adicionar:
# STATS["tool_call_detected"] += 1  # Já existe no proxy
# stats = tool_interceptor.get_stats()
# Adicionar ao /metrics endpoint as métricas do interceptor
'''


if __name__ == "__main__":
    print("=" * 60)
    print("Proxy Tool Interceptor — Deploy Instructions")
    print("=" * 60)
    print()
    print("1. Copiar este arquivo para o homelab:")
    print(f"   scp {__file__} homelab@192.168.15.2:~/llm-optimizer/")
    print()
    print("2. Integrar no proxy:")
    print(DEPLOY_SNIPPET)
    print()
    print(f"3. Tools disponíveis ({len(NATIVE_TOOLS)}):")
    for t in NATIVE_TOOLS:
        name = t["function"]["name"]
        desc = t["function"]["description"][:60]
        print(f"   - {name}: {desc}...")
    print()
    print(f"4. Modelos com suporte ({len(TOOL_CAPABLE_MODELS)}):")
    for m in sorted(TOOL_CAPABLE_MODELS):
        print(f"   - {m}")
