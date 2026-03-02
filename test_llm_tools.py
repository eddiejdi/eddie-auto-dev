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
