"""Cliente simples para Ollama local.

Objetivo: padronizar chamadas ao Ollama (homelab) e habilitar `keep_alive`
para reduzir trocas/overhead e economizar tokens em flows que usam LLM.

Uso exemplo:
    from tools.ollama_client import OllamaClient
    client = OllamaClient()
    resp = client.generate("Resuma estes dados", num_predict=128, timeout=300)

O VALOR de `OLLAMA_HOST` e `OLLAMA_MODEL` é lido de variáveis de ambiente.

Padrão de roteamento:
- GPU0 (:11434) + Phi (solicitações padrão)
- GPU1 (:11435) + modelo pequeno (solicitações curtas)
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
    """Cliente de geração para instâncias Ollama com roteamento dual-GPU."""

    def __init__(self, host: t.Optional[str] = None, model: t.Optional[str] = None, keep_alive: t.Optional[str] = None):
        """Inicializa cliente com defaults GPU-first.

        Args:
            host: Host primário opcional (override de OLLAMA_HOST).
            model: Modelo primário opcional (override de OLLAMA_MODEL).
            keep_alive: Valor opcional para keep_alive do Ollama.
        """
        self.host = host or os.getenv('OLLAMA_HOST', 'http://192.168.15.2:11434')
        self.model = model or os.getenv('OLLAMA_MODEL', 'phi4-mini:latest')
        self.small_host = os.getenv('OLLAMA_HOST_GPU1', 'http://192.168.15.2:11435')
        self.small_model = os.getenv('OLLAMA_SMALL_MODEL', 'qwen3:0.6b')
        self.keep_alive = keep_alive
        if httpx is None:
            raise RuntimeError('httpx não está instalado; instale com `pip install httpx`')
        self._clients: dict[str, httpx.Client] = {
            self.host: httpx.Client(base_url=self.host, timeout=300.0),
        }

    def _payload(self, prompt: str, num_predict: int = 128, num_ctx: int = 1024) -> dict:
        """Monta payload padrão da API /api/generate."""
        payload = {
            'prompt': prompt,
            'num_predict': num_predict,
            'num_ctx': num_ctx,
            'stream': False,
        }
        if self.keep_alive:
            payload['keep_alive'] = self.keep_alive
        return payload

    def _get_client(self, host: str) -> httpx.Client:
        """Retorna cliente HTTP cacheado para o host informado."""
        client = self._clients.get(host)
        if client is not None:
            return client
        client = httpx.Client(base_url=host, timeout=300.0)
        self._clients[host] = client
        return client

    def generate(
        self,
        prompt: str,
        num_predict: int = 128,
        num_ctx: int = 1024,
        timeout: int = 300,
        *,
        small_request: bool = False,
        host: t.Optional[str] = None,
        model: t.Optional[str] = None,
    ) -> dict:
        """Gera texto usando o Ollama.

        Args:
            prompt: Prompt enviado para o modelo.
            num_predict: Máximo de tokens de saída.
            num_ctx: Janela de contexto.
            timeout: Timeout por request em segundos.
            small_request: Se True, usa GPU1 + modelo pequeno por padrão.
            host: Host explícito para sobrescrever roteamento.
            model: Modelo explícito para sobrescrever roteamento.

        Retorna o JSON retornado pelo endpoint `/api/generate`.
        """
        url = '/api/generate'
        payload = self._payload(prompt, num_predict=num_predict, num_ctx=num_ctx)
        selected_host = host or (self.small_host if small_request else self.host)
        selected_model = model or (self.small_model if small_request else self.model)
        payload['model'] = selected_model
        # httpx client tem timeout por request; sobrescrevemos aqui
        resp = self._get_client(selected_host).post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except json.JSONDecodeError:
            return {'response_text': resp.text}

    def close(self) -> None:
        """Fecha todos os clientes HTTP abertos."""
        try:
            for client in self._clients.values():
                client.close()
        except Exception:
            pass


def quick_demo():
    c = OllamaClient(keep_alive='3600s')
    r = c.generate('Hello Ollama — sumarize: 1+1')
    print(r)


if __name__ == '__main__':
    quick_demo()
