"""Cliente simples para Ollama local.

Objetivo: padronizar chamadas ao Ollama (homelab) e habilitar `keep_alive`
para reduzir trocas/overhead e economizar tokens em flows que usam LLM.

Uso exemplo:
    from tools.ollama_client import OllamaClient
    client = OllamaClient()
    resp = client.generate("Resuma estes dados", num_predict=128, timeout=300)

O VALOR de `OLLAMA_HOST` e `OLLAMA_MODEL` é lido de variáveis de ambiente.
"""
from __future__ import annotations

import os
import typing as t
import json

try:
    import httpx
except Exception:  # pragma: no cover - runtime
    httpx = None


class OllamaClient:
    def __init__(self, host: t.Optional[str] = None, model: t.Optional[str] = None, keep_alive: t.Optional[str] = None):
        self.host = host or os.getenv('OLLAMA_HOST', 'http://192.168.15.2:11434')
        self.model = model or os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b')
        self.keep_alive = keep_alive
        if httpx is None:
            raise RuntimeError('httpx não está instalado; instale com `pip install httpx`')
        self._client = httpx.Client(base_url=self.host, timeout=300.0)

    def _payload(self, prompt: str, num_predict: int = 128, num_ctx: int = 1024) -> dict:
        payload = {
            'model': self.model,
            'prompt': prompt,
            'num_predict': num_predict,
            'num_ctx': num_ctx,
            'stream': False,
        }
        if self.keep_alive:
            payload['keep_alive'] = self.keep_alive
        return payload

    def generate(self, prompt: str, num_predict: int = 128, num_ctx: int = 1024, timeout: int = 300) -> dict:
        """Gera texto usando o Ollama.

        Retorna o JSON retornado pelo endpoint `/api/generate`.
        """
        url = '/api/generate'
        payload = self._payload(prompt, num_predict=num_predict, num_ctx=num_ctx)
        # httpx client tem timeout por request; sobrescrevemos aqui
        resp = self._client.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except json.JSONDecodeError:
            return {'response_text': resp.text}

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


def quick_demo():
    c = OllamaClient(keep_alive='3600s')
    r = c.generate('Hello Ollama — sumarize: 1+1')
    print(r)


if __name__ == '__main__':
    quick_demo()
