"""
Modulo de integracao com LLM (Ollama)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import urllib.request
import urllib.error


class AgentRole(str, Enum):
    coder = "coder"
    debugger = "debugger"
    architect = "architect"
    tester = "tester"


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    tokens_used: int = 0
    success: bool = True
    error: str = ""


class LLMClient:
    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.fallback_model: Optional[str] = None
        self._role: AgentRole = AgentRole.coder

    @property
    def system_prompt(self) -> str:
        from dev_agent.config import CODER_PROMPT, DEBUGGER_PROMPT, ARCHITECT_PROMPT, TESTER_PROMPT
        mapping = {
            AgentRole.coder: CODER_PROMPT,
            AgentRole.debugger: DEBUGGER_PROMPT,
            AgentRole.architect: ARCHITECT_PROMPT,
            AgentRole.tester: TESTER_PROMPT,
        }
        return mapping.get(self._role, CODER_PROMPT)

    def set_role(self, role: AgentRole) -> None:
        self._role = role

    def check_connection(self) -> bool:
        try:
            req = urllib.request.Request(self.base_url + "/api/tags")
            with urllib.request.urlopen(req, timeout=10):
                return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            req = urllib.request.Request(self.base_url + "/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or self.system_prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + "/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.load(resp)
                return LLMResponse(
                    content=data.get("response", ""),
                    model=self.model,
                    tokens_used=data.get("eval_count", 0),
                    success=True,
                )
        except Exception as e:
            return LLMResponse(content="", success=False, error=f"Falha na geracao: {e}")

    def generate_sync(self, prompt: str, system: str = "") -> str:
        resp = self.generate(prompt, system=system)
        return resp.content if resp.success else ""


class CodeGenerator:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_code(self, description: str, language: str = "python", requirements: list[str] = None) -> dict:
        req_str = ", ".join(requirements) if requirements else ""
        prompt = f"Crie codigo {language} para: {description}"
        if req_str:
            prompt += f". Requisitos: {req_str}"
        prompt += ". Retorne APENAS o codigo."
        resp = self.llm.generate(prompt)
        return {"success": resp.success, "code": self._extract_code(resp.content), "error": resp.error}

    def fix_code(self, code: str, error: str, language: str = "python") -> dict:
        prompt = (
            f"Codigo com erro:\n```{language}\n{code}\n```\n"
            f"Erro: {error}\nCorrija e retorne APENAS o codigo corrigido."
        )
        resp = self.llm.generate(prompt)
        return {"success": resp.success, "code": self._extract_code(resp.content)}

    def generate_tests(self, code: str) -> str:
        prompt = f"Crie testes pytest para:\n```python\n{code}\n```\nRetorne APENAS o codigo de teste."
        resp = self.llm.generate(prompt)
        return self._extract_code(resp.content)

    def _extract_code(self, content: str) -> str:
        match = re.search(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
        return match.group(1).strip() if match else content.strip()


class ConversationManager:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self._history: list[dict] = []

    def add_message(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})

    def send(self, message: str) -> str:
        self.add_message("user", message)
        context = "\n".join(f"{m['role']}: {m['content']}" for m in self._history)
        resp = self.llm.generate(context)
        result = resp.content if resp.success else f"Erro: {resp.error}"
        self.add_message("assistant", result)
        return result

    def clear_history(self) -> None:
        self._history.clear()
