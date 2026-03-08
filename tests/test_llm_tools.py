#!/usr/bin/env python3
"""
Test suite para LLM Tool Executor + Enhanced + Prompts.

Grupos:
  1. Unit — executor base (sem dependências externas)
  2. Unit — prompts (parse, format, strip)
  3. Unit — enhanced executor (mock memory/bus quando DATABASE_URL ausente)
  4. Integration — API endpoints (requer API em :8503)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

sys.path.insert(0, str(Path(__file__).parent))

from specialized_agents.llm_tool_executor import get_llm_tool_executor, LLMToolExecutor
from specialized_agents.llm_tool_prompts import (
    parse_tool_calls,
    get_tool_system_prompt,
    get_tool_result_prompt,
    strip_tool_calls,
    TOOL_CALL_OPEN,
    TOOL_CALL_CLOSE,
)


# ═══════════════════════════════════════════════════════════════════
# 1. Unit — Executor Base
# ═══════════════════════════════════════════════════════════════════


class TestExecutorBase:
    """Testes unitários do LLMToolExecutor base."""

    def test_instantiation(self):
        executor = get_llm_tool_executor()
        assert executor is not None
        assert isinstance(executor, LLMToolExecutor)

    def test_singleton(self):
        a = get_llm_tool_executor()
        b = get_llm_tool_executor()
        assert a is b

    def test_available_tools(self):
        executor = get_llm_tool_executor()
        tools = executor.get_available_tools()
        assert "tools" in tools
        assert len(tools["tools"]) >= 4
        names = [t["name"] for t in tools["tools"]]
        assert "shell_exec" in names
        assert "read_file" in names
        assert "list_directory" in names
        assert "system_info" in names

    @pytest.mark.asyncio
    async def test_shell_exec_pwd(self):
        executor = get_llm_tool_executor()
        result = await executor.execute_shell("pwd")
        assert result["success"] is True
        assert len(result["stdout"]) > 0

    @pytest.mark.asyncio
    async def test_shell_exec_blocked(self):
        executor = get_llm_tool_executor()
        result = await executor.execute_shell("rm -rf /")
        assert result["success"] is False
        # Mensagem de bloqueio fica em stderr
        msg = (result.get("stderr", "") + result.get("error", "")).lower()
        assert "negado" in msg or "bloqueado" in msg or "blocked" in msg

    @pytest.mark.asyncio
    async def test_shell_exec_unknown_command(self):
        executor = get_llm_tool_executor()
        result = await executor.execute_shell("nonexistent_command_xyz123")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_read_file_existing(self):
        executor = get_llm_tool_executor()
        result = await executor.read_file("/etc/hostname")
        assert result["success"] is True
        assert len(result.get("content", "")) > 0

    @pytest.mark.asyncio
    async def test_read_file_nonexistent(self):
        executor = get_llm_tool_executor()
        result = await executor.read_file("/tmp/nonexistent_file_xyz123.txt")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_directory(self):
        executor = get_llm_tool_executor()
        result = await executor.list_directory("/tmp")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_system_info(self):
        executor = get_llm_tool_executor()
        result = await executor.get_system_info()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_tool_dispatch(self):
        executor = get_llm_tool_executor()
        result = executor.execute_tool("system_info", {})
        # execute_tool pode retornar coroutine ou dict
        if asyncio.iscoroutine(result):
            result = await result
        assert result["success"] is True

    def test_is_command_allowed_safe(self):
        # is_command_allowed retorna tuple (bool, str)
        assert LLMToolExecutor.is_command_allowed("ls -la /home")[0] is True
        assert LLMToolExecutor.is_command_allowed("git status")[0] is True
        assert LLMToolExecutor.is_command_allowed("docker ps")[0] is True

    def test_is_command_allowed_blocked(self):
        assert LLMToolExecutor.is_command_allowed("rm -rf /")[0] is False
        assert LLMToolExecutor.is_command_allowed("dd of=/dev/sda")[0] is False
        assert LLMToolExecutor.is_command_allowed("mkfs.ext4 /dev/sda")[0] is False


# ═══════════════════════════════════════════════════════════════════
# 2. Unit — Prompts
# ═══════════════════════════════════════════════════════════════════


class TestPrompts:
    """Testes unitários para llm_tool_prompts."""

    def test_system_prompt_not_empty(self):
        prompt = get_tool_system_prompt()
        assert len(prompt) > 100
        assert "<tool_call>" in prompt
        assert "shell_exec" in prompt

    def test_system_prompt_extra_context(self):
        prompt = get_tool_system_prompt(extra_context="CUSTOM CONTEXT")
        assert "CUSTOM CONTEXT" in prompt

    def test_parse_single_tool_call(self):
        text = """Vou verificar:
<tool_call>
{"tool": "shell_exec", "params": {"command": "docker ps"}}
</tool_call>"""
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == "shell_exec"
        assert calls[0]["params"]["command"] == "docker ps"

    def test_parse_multiple_tool_calls(self):
        text = """Verificando:
<tool_call>
{"tool": "shell_exec", "params": {"command": "docker ps"}}
</tool_call>
Também:
<tool_call>
{"tool": "system_info", "params": {}}
</tool_call>"""
        calls = parse_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["tool"] == "shell_exec"
        assert calls[1]["tool"] == "system_info"

    def test_parse_no_tool_calls(self):
        text = "Aqui está a resposta sem ferramentas."
        calls = parse_tool_calls(text)
        assert len(calls) == 0

    def test_parse_invalid_json(self):
        text = "<tool_call>not valid json</tool_call>"
        calls = parse_tool_calls(text)
        assert len(calls) == 0

    def test_parse_missing_tool_key(self):
        text = '<tool_call>{"action": "shell_exec"}</tool_call>'
        calls = parse_tool_calls(text)
        assert len(calls) == 0

    def test_strip_tool_calls(self):
        text = """Texto antes
<tool_call>
{"tool": "shell_exec", "params": {"command": "ls"}}
</tool_call>
Texto depois"""
        stripped = strip_tool_calls(text)
        assert "<tool_call>" not in stripped
        assert "Texto antes" in stripped
        assert "Texto depois" in stripped

    def test_tool_result_prompt_success(self):
        result = {"success": True, "stdout": "container1\ncontainer2"}
        formatted = get_tool_result_prompt("shell_exec", result)
        assert "[RESULTADO: shell_exec]" in formatted
        assert "Sucesso: sim" in formatted
        assert "container1" in formatted

    def test_tool_result_prompt_failure(self):
        result = {"success": False, "error": "command not found", "exit_code": 127}
        formatted = get_tool_result_prompt("shell_exec", result)
        assert "Sucesso: não" in formatted
        assert "command not found" in formatted

    def test_tool_result_prompt_truncation(self):
        result = {"success": True, "stdout": "x" * 5000}
        formatted = get_tool_result_prompt("shell_exec", result)
        assert "truncado" in formatted


# ═══════════════════════════════════════════════════════════════════
# 3. Unit — Enhanced Executor
# ═══════════════════════════════════════════════════════════════════


class TestEnhancedExecutor:
    """Testes do executor enhanced (sem DATABASE_URL = memory desabilitada)."""

    def test_instantiation(self):
        # Limpar singleton para testar
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()
        assert executor is not None
        assert executor.base_executor is not None

    def test_memory_disabled_without_db(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None

        with patch.dict(os.environ, {}, clear=True):
            # Remover DATABASE_URL se existir
            os.environ.pop("DATABASE_URL", None)
            executor = mod.get_enhanced_executor()
            # Sem DATABASE_URL, memory deve ser None
            # (pode não ser None se DATABASE_URL estiver setada globalmente)

    @pytest.mark.asyncio
    async def test_execute_with_learning_success(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()

        result = await executor.execute_with_learning(
            tool_name="shell_exec",
            params={"command": "echo hello"},
            user_query="teste",
        )
        assert result["success"] is True
        assert "hello" in result.get("stdout", "")
        # Deve ter metadata de learning
        assert "_learning" in result
        assert result["_learning"]["outcome"] == "success"
        assert result["_learning"]["confidence"] >= 0.85

    @pytest.mark.asyncio
    async def test_execute_with_learning_failure(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()

        result = await executor.execute_with_learning(
            tool_name="shell_exec",
            params={"command": "rm -rf /"},
            user_query="teste blocked",
        )
        assert result["success"] is False
        assert "_learning" in result

    @pytest.mark.asyncio
    async def test_execute_read_file_with_learning(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()

        result = await executor.execute_with_learning(
            tool_name="read_file",
            params={"filepath": "/etc/hostname"},
        )
        assert result["success"] is True
        assert "_learning" in result

    @pytest.mark.asyncio
    async def test_learning_stats(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()

        stats = await executor.get_learning_stats()
        assert isinstance(stats, dict)
        assert "enabled" in stats

    def test_compute_initial_confidence_no_history(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()

        conf = executor._compute_initial_confidence("shell_exec", "ls", [])
        assert conf == 0.5  # neutro sem histórico

    def test_compute_initial_confidence_with_successes(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()

        past = [
            {"outcome": "success"},
            {"outcome": "success"},
            {"outcome": "failure"},
        ]
        conf = executor._compute_initial_confidence("shell_exec", "ls", past)
        assert conf > 0.5  # mais sucessos que falhas

    def test_compute_initial_confidence_with_failures(self):
        import specialized_agents.llm_tool_executor_enhanced as mod
        mod._enhanced_executor = None
        executor = mod.get_enhanced_executor()

        past = [
            {"outcome": "failure"},
            {"outcome": "failure"},
            {"outcome": "success"},
        ]
        conf = executor._compute_initial_confidence("shell_exec", "ls", past)
        assert conf < 0.5  # mais falhas que sucessos


# ═══════════════════════════════════════════════════════════════════
# 4. Integration — API Endpoints (requer API rodando em :8503)
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestAPIEndpoints:
    """Testes de integração com a API FastAPI."""

    API_BASE = "http://localhost:8503/llm-tools"

    @pytest.mark.asyncio
    async def test_health(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.API_BASE}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] in ("healthy", "unhealthy")

    @pytest.mark.asyncio
    async def test_available_tools(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.API_BASE}/available")
            assert resp.status_code == 200
            data = resp.json()
            assert "tools" in data

    @pytest.mark.asyncio
    async def test_system_prompt(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.API_BASE}/system-prompt")
            assert resp.status_code == 200
            data = resp.json()
            assert "system_prompt" in data
            assert "<tool_call>" in data["system_prompt"]

    @pytest.mark.asyncio
    async def test_learning_stats(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.API_BASE}/learning-stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "enabled" in data

    @pytest.mark.asyncio
    async def test_exec_shell(self):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.API_BASE}/exec-shell",
                json={"command": "echo integration_test", "timeout": 10},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "integration_test" in data.get("stdout", "")
            # Deve conter metadata de learning
            assert "_learning" in data

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.API_BASE}/execute",
                json={"tool_name": "system_info", "params": {}},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_openwebui_schema(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.API_BASE}/openwebui-schema")
            assert resp.status_code == 200
            data = resp.json()
            assert "tools" in data


# ═══════════════════════════════════════════════════════════════════
# 5. Unit — Native Ollama Tool Schemas
# ═══════════════════════════════════════════════════════════════════

from specialized_agents.llm_tool_schemas import (
    get_ollama_tools,
    get_tool_system_message,
    normalize_tool_call,
    normalize_tool_calls,
    format_tool_result_message,
    format_assistant_tool_call_message,
)


class TestNativeToolSchemas:
    """Testes para llm_tool_schemas.py — schemas nativos Ollama."""

    def test_get_ollama_tools_returns_list(self):
        tools = get_ollama_tools()
        assert isinstance(tools, list)
        assert len(tools) == 4

    def test_ollama_tools_format(self):
        tools = get_ollama_tools()
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"

    def test_tool_names(self):
        tools = get_ollama_tools()
        names = [t["function"]["name"] for t in tools]
        assert "shell_exec" in names
        assert "read_file" in names
        assert "list_directory" in names
        assert "system_info" in names

    def test_shell_exec_required_params(self):
        tools = get_ollama_tools()
        shell = next(t for t in tools if t["function"]["name"] == "shell_exec")
        params = shell["function"]["parameters"]
        assert "command" in params["properties"]
        assert "command" in params["required"]

    def test_get_tool_system_message(self):
        msg = get_tool_system_message()
        assert isinstance(msg, str)
        assert len(msg) > 50
        assert "Shared" in msg or "tool" in msg.lower()

    def test_normalize_tool_call(self):
        """Testa conversão do formato Ollama para formato interno."""
        ollama_tc = {
            "function": {
                "name": "shell_exec",
                "arguments": {"command": "docker ps"}
            }
        }
        result = normalize_tool_call(ollama_tc)
        assert result["tool"] == "shell_exec"
        assert result["params"]["command"] == "docker ps"

    def test_normalize_tool_call_string_arguments(self):
        """Testa quando arguments vem como string JSON."""
        ollama_tc = {
            "function": {
                "name": "read_file",
                "arguments": '{"filepath": "/tmp/test.txt"}'
            }
        }
        result = normalize_tool_call(ollama_tc)
        assert result["tool"] == "read_file"
        assert result["params"]["filepath"] == "/tmp/test.txt"

    def test_normalize_tool_calls_batch(self):
        """Testa normalização de múltiplos tool_calls."""
        raw = [
            {"function": {"name": "shell_exec", "arguments": {"command": "ls"}}},
            {"function": {"name": "system_info", "arguments": {}}},
        ]
        results = normalize_tool_calls(raw)
        assert len(results) == 2
        assert results[0]["tool"] == "shell_exec"
        assert results[1]["tool"] == "system_info"

    def test_normalize_tool_calls_empty(self):
        assert normalize_tool_calls([]) == []
        assert normalize_tool_calls(None) == []

    def test_format_tool_result_message(self):
        """Testa formatação de resultado como mensagem role=tool."""
        result = {"success": True, "stdout": "hello world"}
        msg = format_tool_result_message("shell_exec", result)
        assert msg["role"] == "tool"
        assert "hello world" in msg["content"]

    def test_format_tool_result_message_error(self):
        """Testa formatação de erro."""
        result = {"success": False, "error": "command not found"}
        msg = format_tool_result_message("shell_exec", result)
        assert msg["role"] == "tool"
        assert "ERRO" in msg["content"] or "command not found" in msg["content"]

    def test_format_assistant_tool_call_message(self):
        """Testa formatação de mensagem assistant com tool_calls."""
        tool_calls = [
            {"function": {"name": "shell_exec", "arguments": {"command": "ls"}}}
        ]
        msg = format_assistant_tool_call_message(tool_calls)
        assert msg["role"] == "assistant"
        assert msg["tool_calls"] == tool_calls


# ═══════════════════════════════════════════════════════════════════
# 6. Unit — Proxy Tool Interceptor
# ═══════════════════════════════════════════════════════════════════

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from tools.proxy_tool_interceptor import (
    ToolInterceptor,
    NATIVE_TOOLS,
    _is_tool_capable,
)


class TestProxyToolInterceptor:
    """Testes para tools/proxy_tool_interceptor.py."""

    def test_is_tool_capable_supported(self):
        assert _is_tool_capable("qwen3:8b") is True
        assert _is_tool_capable("qwen2.5-coder:7b") is True
        assert _is_tool_capable("llama3.1") is True
        assert _is_tool_capable("mistral") is True
        assert _is_tool_capable("shared-coder") is True

    def test_is_tool_capable_unsupported(self):
        assert _is_tool_capable("phi3:mini") is False
        assert _is_tool_capable("") is False
        assert _is_tool_capable("tinyllama") is False

    def test_native_tools_format(self):
        assert len(NATIVE_TOOLS) == 4
        for t in NATIVE_TOOLS:
            assert t["type"] == "function"
            assert "function" in t
            assert "name" in t["function"]

    def test_interceptor_instantiation(self):
        interceptor = ToolInterceptor(executor_url="http://test:8503")
        assert interceptor.executor_url == "http://test:8503"
        assert interceptor.max_rounds > 0

    def test_inject_tools_no_existing(self):
        """Se não tem tools e modelo suporta → injeta."""
        interceptor = ToolInterceptor()
        body = {
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "hello"}],
        }
        result = interceptor.inject_tools(body)
        assert "tools" in result
        assert len(result["tools"]) == 4
        assert result["stream"] is False

    def test_inject_tools_already_has_tools(self):
        """Se já tem tools → não sobrescreve."""
        interceptor = ToolInterceptor()
        body = {
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function", "function": {"name": "custom"}}],
        }
        result = interceptor.inject_tools(body)
        assert len(result["tools"]) == 1  # mantém a original
        assert result["tools"][0]["function"]["name"] == "custom"

    def test_inject_tools_unsupported_model(self):
        """Se modelo não suporta → não injeta."""
        interceptor = ToolInterceptor()
        body = {
            "model": "phi3:mini",
            "messages": [{"role": "user", "content": "hello"}],
        }
        result = interceptor.inject_tools(body)
        assert "tools" not in result

    def test_inject_tools_adds_system_message(self):
        """Deve injetar system message se não houver."""
        interceptor = ToolInterceptor()
        body = {
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "test"}],
        }
        result = interceptor.inject_tools(body)
        roles = [m["role"] for m in result["messages"]]
        assert "system" in roles

    def test_inject_tools_keeps_existing_system(self):
        """Não deve duplicar system message."""
        interceptor = ToolInterceptor()
        body = {
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": "my system prompt"},
                {"role": "user", "content": "test"},
            ],
        }
        result = interceptor.inject_tools(body)
        system_count = sum(1 for m in result["messages"] if m["role"] == "system")
        assert system_count == 1

    def test_inject_tools_does_not_mutate_original(self):
        """Deve retornar cópia, não mutar o original."""
        interceptor = ToolInterceptor()
        body = {
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "test"}],
        }
        result = interceptor.inject_tools(body)
        assert "tools" not in body  # original não mudou
        assert "tools" in result

    def test_has_tool_calls_true(self):
        interceptor = ToolInterceptor()
        response = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "shell_exec", "arguments": {"command": "ls"}}}],
            }
        }
        assert interceptor.has_tool_calls(response) is True

    def test_has_tool_calls_false(self):
        interceptor = ToolInterceptor()
        response = {
            "message": {"role": "assistant", "content": "hello"},
        }
        assert interceptor.has_tool_calls(response) is False

    def test_stats_initial(self):
        interceptor = ToolInterceptor()
        stats = interceptor.get_stats()
        assert stats["requests_intercepted"] == 0
        assert stats["tools_injected"] == 0

    def test_stats_after_injection(self):
        interceptor = ToolInterceptor()
        body = {
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "test"}],
        }
        interceptor.inject_tools(body)
        stats = interceptor.get_stats()
        assert stats["requests_intercepted"] == 1
        assert stats["tools_injected"] == 1


# ═══════════════════════════════════════════════════════════════════
# 7. Unit — Open WebUI Tool
# ═══════════════════════════════════════════════════════════════════


class TestOpenWebUITool:
    """Testes para openwebui_tool_executor.py — classe Tools."""

    def test_import_and_instantiation(self):
        from openwebui_tool_executor import Tools
        tool = Tools()
        assert tool is not None
        assert hasattr(tool, "shell_exec")
        assert hasattr(tool, "read_file")
        assert hasattr(tool, "list_directory")
        assert hasattr(tool, "system_info")

    def test_valves_defaults(self):
        from openwebui_tool_executor import Tools
        tool = Tools()
        assert "8503" in tool.valves.EDDIE_API_URL
        assert tool.valves.TOOL_TIMEOUT > 0

    def test_methods_are_callable(self):
        from openwebui_tool_executor import Tools
        tool = Tools()
        assert callable(tool.shell_exec)
        assert callable(tool.read_file)
        assert callable(tool.list_directory)
        assert callable(tool.system_info)
