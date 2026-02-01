"""
Modulo de integracao com LLM (Ollama)
"""

import httpx
import asyncio
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from .config import LLM_CONFIG, SYSTEM_PROMPTS


class AgentRole(Enum):
    CODER = "coder"
    DEBUGGER = "debugger"
    ARCHITECT = "architect"
    TESTER = "tester"


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_used: int
    success: bool
    error: Optional[str] = None


class LLMClient:
    def __init__(self, base_url: str = None, model: str = None, timeout: int = None):
        self.base_url = base_url or LLM_CONFIG["base_url"]
        self.model = model or LLM_CONFIG["model"]
        self.timeout = timeout or LLM_CONFIG["timeout"]
        self.fallback_model = LLM_CONFIG["fallback_model"]
        self._current_role = AgentRole.CODER

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPTS.get(self._current_role.value, SYSTEM_PROMPTS["coder"])

    def set_role(self, role: AgentRole):
        self._current_role = role

    async def check_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]
        except:
            pass
        return []

    async def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> LLMResponse:
        system_prompt = system or self.system_prompt
        temp = temperature or LLM_CONFIG["temperature"]
        tokens = max_tokens or LLM_CONFIG["max_tokens"]

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": temp, "num_predict": tokens},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate", json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    return LLMResponse(
                        content=data.get("response", ""),
                        model=self.model,
                        tokens_used=data.get("eval_count", 0),
                        success=True,
                    )
        except Exception:
            pass

        return LLMResponse(
            content="",
            model=self.model,
            tokens_used=0,
            success=False,
            error="Falha na geracao",
        )

    def generate_sync(self, prompt: str, system: str = None) -> LLMResponse:
        return asyncio.run(self.generate(prompt, system))


class CodeGenerator:
    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()

    async def generate_code(
        self, description: str, language: str = "python", requirements: List[str] = None
    ) -> Dict[str, Any]:
        self.llm.set_role(AgentRole.CODER)
        prompt = f"Crie codigo {language} para: {description}. Retorne APENAS o codigo."
        response = await self.llm.generate(prompt)

        if response.success:
            code = self._extract_code(response.content)
            return {"success": True, "code": code, "language": language}
        return {"success": False, "error": response.error, "code": ""}

    async def fix_code(
        self, code: str, error: str, language: str = "python"
    ) -> Dict[str, Any]:
        self.llm.set_role(AgentRole.DEBUGGER)
        prompt = f"Codigo com erro:\n```{language}\n{code}\n```\nErro: {error}\nCorrija e retorne APENAS o codigo corrigido."
        response = await self.llm.generate(prompt)

        if response.success:
            return {"success": True, "code": self._extract_code(response.content)}
        return {"success": False, "error": response.error, "code": code}

    async def generate_tests(self, code: str) -> Dict[str, Any]:
        self.llm.set_role(AgentRole.TESTER)
        prompt = f"Crie testes pytest para:\n```python\n{code}\n```\nRetorne APENAS o codigo de teste."
        response = await self.llm.generate(prompt)

        if response.success:
            return {"success": True, "test_code": self._extract_code(response.content)}
        return {"success": False, "error": response.error}

    def _extract_code(self, content: str) -> str:
        pattern = r"```(?:\w+)?\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)
        return matches[0].strip() if matches else content.strip()


class ConversationManager:
    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()
        self.history: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > 20:
            self.history = self.history[-20:]

    async def send(self, message: str) -> str:
        self.add_message("user", message)
        parts = [f"{m['role']}: {m['content']}" for m in self.history]
        full_prompt = "\n".join(parts)
        response = await self.llm.generate(full_prompt)

        if response.success:
            self.add_message("assistant", response.content)
            return response.content
        return f"Erro: {response.error}"

    def clear_history(self):
        self.history = []
