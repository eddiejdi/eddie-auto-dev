"""Thin bridge that exposes an MCP-style run_with_tools interface over OllamaClient.

Designed for callers that pass tools=[] and only need plain LLM generation.
"""
from __future__ import annotations

import os
from typing import Any, List, Optional

from tools.ollama_client import OllamaClient


class OllamaMCPBridge:
    """Context-manager wrapper around OllamaClient with a run_with_tools interface."""

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        num_ctx: int = 8192,
        num_predict: int = 2048,
        timeout: int = 300,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_TRADING_MODEL", "trading-analyst:latest")
        self.host = host or os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.timeout = timeout
        self._client: Optional[OllamaClient] = None

    def __enter__(self) -> "OllamaMCPBridge":
        self._client = OllamaClient(host=self.host, model=self.model)
        return self

    def __exit__(self, *_: Any) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def run_with_tools(
        self,
        user_msg: str,
        system: str = "",
        tools: List[Any] = [],
    ) -> str:
        """Run inference. tools=[] means plain generation (no MCP tool calls)."""
        if self._client is None:
            raise RuntimeError("OllamaMCPBridge must be used as a context manager")

        prompt = f"{system}\n\n{user_msg}".strip() if system else user_msg

        resp = self._client.generate(
            prompt=prompt,
            num_predict=self.num_predict,
            num_ctx=self.num_ctx,
            timeout=self.timeout,
            model=self.model,
            host=self.host,
        )
        return resp.get("response", resp.get("response_text", ""))
