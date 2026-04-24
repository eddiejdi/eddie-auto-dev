"""Cliente simples para Ollama local.

Objetivo: padronizar chamadas ao Ollama (homelab) e habilitar `keep_alive`
para reduzir trocas/overhead e economizar tokens em flows que usam LLM.

Uso exemplo:
    from tools.ollama_client import OllamaClient
    client = OllamaClient()
    resp = client.generate("Resuma estes dados", num_predict=128, timeout=300)

O VALOR de `OLLAMA_HOST` e `OLLAMA_MODEL` é lido de variáveis de ambiente.

Padrão de roteamento:
- GPU0 (:11434) + modelo geral existente (solicitações expert)
- GPU1 (:11435) + modelo pequeno (solicitações curtas)
"""
from __future__ import annotations

import os
import typing as t
import json
import re

try:
    import httpx
except Exception:  # pragma: no cover - runtime
    httpx = None


class OllamaClient:
    """Cliente de geração para instâncias Ollama com roteamento dual-GPU."""

    _EXPERT_KEYWORDS = (
        "debug",
        "depurar",
        "refactor",
        "refator",
        "arquitetura",
        "architecture",
        "implement",
        "implementar",
        "function",
        "class",
        "classe",
        "codigo",
        "código",
        "teste",
        "test ",
        "review",
        "analise",
        "análise",
        "error",
        "stacktrace",
        "traceback",
    )

    def __init__(self, host: t.Optional[str] = None, model: t.Optional[str] = None, keep_alive: t.Optional[str] = None):
        """Inicializa cliente com defaults GPU-first.

        Args:
            host: Host primário opcional (override de OLLAMA_HOST).
            model: Modelo primário opcional (override de OLLAMA_MODEL).
            keep_alive: Valor opcional para keep_alive do Ollama.
        """
        self.host = host or os.getenv('OLLAMA_HOST', 'http://192.168.15.2:11434')
        self.model = model or os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')
        self.small_host = os.getenv('OLLAMA_HOST_GPU1', 'http://192.168.15.2:11435')
        self.small_model = os.getenv('OLLAMA_SMALL_MODEL', 'qwen3:0.6b')
        self.keep_alive = keep_alive
        self.auto_route_small = os.getenv('OLLAMA_AUTO_ROUTE_SMALL', 'true').lower() not in {'0', 'false', 'no'}
        self.auto_small_max_prompt_chars = int(os.getenv('OLLAMA_AUTO_SMALL_MAX_PROMPT_CHARS', '400'))
        self.auto_small_max_num_predict = int(os.getenv('OLLAMA_AUTO_SMALL_MAX_NUM_PREDICT', '256'))
        self.auto_small_max_num_ctx = int(os.getenv('OLLAMA_AUTO_SMALL_MAX_NUM_CTX', '2048'))
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

    @staticmethod
    def _extract_text(data: dict) -> str:
        """Extrai texto da resposta padronizando chaves mais comuns."""
        for key in ('response', 'response_text', 'text'):
            value = data.get(key)
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
        return ''

    @staticmethod
    def _normalize_validator_result(result: t.Any) -> tuple[bool, str]:
        """Normaliza resultado de validator em `ok, reason`."""
        if isinstance(result, tuple):
            ok = bool(result[0])
            reason = str(result[1]).strip() if len(result) > 1 and result[1] is not None else ''
            return ok, reason
        return bool(result), ''

    @staticmethod
    def _build_retry_prompt(original_prompt: str, previous_text: str, reason: str) -> str:
        """Cria prompt de reparo quando a primeira saída falha na validação."""
        failure_reason = reason or 'saida invalida'
        previous_section = previous_text or '(vazio)'
        return (
            "O pedido original foi:\n"
            f"{original_prompt}\n\n"
            "A resposta anterior falhou na validacao.\n"
            f"Motivo: {failure_reason}\n\n"
            "Resposta anterior:\n"
            f"{previous_section}\n\n"
            "Reescreva a resposta final do zero, corrigindo o problema acima. "
            "Retorne apenas a nova resposta."
        )

    @staticmethod
    def _strip_json_wrappers(text: str) -> str:
        """Remove cercas markdown e texto periférico em torno de JSON."""
        cleaned = text.strip()
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            cleaned = fenced.group(1).strip()
        start_candidates = [idx for idx in (cleaned.find('{'), cleaned.find('[')) if idx != -1]
        if not start_candidates:
            return cleaned
        start = min(start_candidates)
        end = max(cleaned.rfind('}'), cleaned.rfind(']'))
        if end >= start:
            return cleaned[start:end + 1].strip()
        return cleaned

    def _should_auto_route_small(self, prompt: str, num_predict: int, num_ctx: int) -> bool:
        """Decide se uma request curta deve ir para a GPU1 automaticamente."""
        if not self.auto_route_small:
            return False
        if num_predict > self.auto_small_max_num_predict:
            return False
        if num_ctx > self.auto_small_max_num_ctx:
            return False
        prompt_normalized = " ".join(prompt.lower().split())
        if len(prompt_normalized) > self.auto_small_max_prompt_chars:
            return False
        if any(keyword in prompt_normalized for keyword in self._EXPERT_KEYWORDS):
            return False
        return True

    def _should_use_small_request(
        self,
        prompt: str,
        num_predict: int,
        num_ctx: int,
        small_request: t.Optional[bool],
    ) -> bool:
        """Resolve roteamento explícito vs automático."""
        if small_request is not None:
            return small_request
        return self._should_auto_route_small(prompt, num_predict, num_ctx)

    def generate(
        self,
        prompt: str,
        num_predict: int = 128,
        num_ctx: int = 1024,
        timeout: int = 300,
        *,
        small_request: t.Optional[bool] = None,
        host: t.Optional[str] = None,
        model: t.Optional[str] = None,
    ) -> dict:
        """Gera texto usando o Ollama.

        Args:
            prompt: Prompt enviado para o modelo.
            num_predict: Máximo de tokens de saída.
            num_ctx: Janela de contexto.
            timeout: Timeout por request em segundos.
            small_request:
                Se True, força GPU1.
                Se False, força GPU0.
                Se None, aplica heurística para requests curtas.
            host: Host explícito para sobrescrever roteamento.
            model: Modelo explícito para sobrescrever roteamento.

        Retorna o JSON retornado pelo endpoint `/api/generate`.
        """
        url = '/api/generate'
        payload = self._payload(prompt, num_predict=num_predict, num_ctx=num_ctx)
        use_small_request = self._should_use_small_request(prompt, num_predict, num_ctx, small_request)
        selected_host = host or (self.small_host if use_small_request else self.host)
        selected_model = model or (self.small_model if use_small_request else self.model)
        payload['model'] = selected_model
        # httpx client tem timeout por request; sobrescrevemos aqui
        resp = self._get_client(selected_host).post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except json.JSONDecodeError:
            return {'response_text': resp.text}

    def generate_text(
        self,
        prompt: str,
        num_predict: int = 128,
        num_ctx: int = 1024,
        timeout: int = 300,
        *,
        small_request: t.Optional[bool] = None,
        host: t.Optional[str] = None,
        model: t.Optional[str] = None,
    ) -> str:
        """Gera texto simples extraindo a melhor chave disponível."""
        result = self.generate(
            prompt,
            num_predict=num_predict,
            num_ctx=num_ctx,
            timeout=timeout,
            small_request=small_request,
            host=host,
            model=model,
        )
        return self._extract_text(result)

    def generate_validated(
        self,
        prompt: str,
        *,
        validator: t.Optional[t.Callable[[str], t.Any]] = None,
        repair_prompt_builder: t.Optional[t.Callable[[str, str, str], str]] = None,
        max_attempts: int = 2,
        num_predict: int = 128,
        num_ctx: int = 1024,
        timeout: int = 300,
        small_request: t.Optional[bool] = None,
        host: t.Optional[str] = None,
        model: t.Optional[str] = None,
    ) -> str:
        """Gera texto com validação explícita e um retry de reparo."""
        if max_attempts < 1:
            raise ValueError('max_attempts deve ser >= 1')
        validation = validator or (lambda text: (bool(text.strip()), 'resposta vazia'))
        retry_builder = repair_prompt_builder or self._build_retry_prompt
        current_prompt = prompt
        last_text = ''
        last_reason = 'resposta vazia'

        for attempt in range(1, max_attempts + 1):
            result = self.generate(
                current_prompt,
                num_predict=num_predict,
                num_ctx=num_ctx,
                timeout=timeout,
                small_request=small_request,
                host=host,
                model=model,
            )
            candidate = self._extract_text(result)
            ok, reason = self._normalize_validator_result(validation(candidate))
            if ok:
                return candidate
            last_text = candidate
            last_reason = reason or 'resposta rejeitada pela validacao'
            if attempt < max_attempts:
                current_prompt = retry_builder(prompt, candidate, last_reason)

        raise ValueError(f'Falha na validacao apos {max_attempts} tentativa(s): {last_reason}')

    def generate_json(
        self,
        prompt: str,
        *,
        validator: t.Optional[t.Callable[[t.Any], t.Any]] = None,
        max_attempts: int = 2,
        num_predict: int = 256,
        num_ctx: int = 2048,
        timeout: int = 300,
        small_request: t.Optional[bool] = None,
        host: t.Optional[str] = None,
        model: t.Optional[str] = None,
    ) -> t.Any:
        """Gera JSON válido com retry automático quando o parse falha."""
        if max_attempts < 1:
            raise ValueError('max_attempts deve ser >= 1')
        base_prompt = (
            f"{prompt}\n\n"
            "Retorne apenas JSON valido, sem markdown, comentarios ou texto adicional."
        )
        current_prompt = base_prompt
        last_error = 'json invalido'

        for attempt in range(1, max_attempts + 1):
            text = self.generate_text(
                current_prompt,
                num_predict=num_predict,
                num_ctx=num_ctx,
                timeout=timeout,
                small_request=small_request,
                host=host,
                model=model,
            )
            candidate = self._strip_json_wrappers(text)
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = f'json invalido: {exc.msg}'
            else:
                if validator is None:
                    return parsed
                ok, reason = self._normalize_validator_result(validator(parsed))
                if ok:
                    return parsed
                last_error = reason or 'json rejeitado pela validacao'
            if attempt < max_attempts:
                current_prompt = (
                    f"{base_prompt}\n\n"
                    f"O JSON anterior falhou.\nMotivo: {last_error}\n\n"
                    f"Saida anterior:\n{text or '(vazio)'}\n\n"
                    "Responda novamente com JSON valido e nada mais."
                )

        raise ValueError(f'Falha ao gerar JSON apos {max_attempts} tentativa(s): {last_error}')

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
