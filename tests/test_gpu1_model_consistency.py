"""Guarda o modelo da GPU1 contra desvio entre config e realidade.

Contexto: a GPU1 passou de `gemma3-fast:gpu1` para `lfm2.5-fast:gpu1` em
2026-07-10, mas vários lugares continuaram apontando para o modelo antigo.
Apontar para um modelo NÃO residente força o Ollama a subir um runner novo; com
OLLAMA_MAX_LOADED_MODELS=1 isso devolve 503 "maximum pending requests exceeded"
(ver tests/test_ollama_num_ctx_consistency.py — mesma classe de defeito).

`deploy/crypto-agent/models.env` é a fonte de verdade declarada ("edite APENAS
este arquivo para trocar de modelo"). Estes testes exigem que os demais pontos
não a contradigam.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
MODELS_ENV = RAIZ / "deploy" / "crypto-agent" / "models.env"


@pytest.fixture(scope="module")
def modelo_gpu1() -> str:
    """Lê o modelo da GPU1 da fonte de verdade (models.env)."""
    texto = MODELS_ENV.read_text(encoding="utf-8")
    match = re.search(r"^OLLAMA_SMALL_MODEL=(\S+)\s*$", texto, re.MULTILINE)
    assert match, "OLLAMA_SMALL_MODEL não encontrado em models.env"
    return match.group(1)


def test_models_env_define_modelo_gpu1(modelo_gpu1: str) -> None:
    assert modelo_gpu1.endswith(":gpu1"), (
        f"OLLAMA_SMALL_MODEL={modelo_gpu1!r} deveria ter sufixo :gpu1 — "
        "o coordinator usa esse sufixo para pinar o roteamento na GPU1."
    )


def test_fallbacks_do_models_env_usam_o_modelo_da_gpu1(modelo_gpu1: str) -> None:
    """Todos os *_FALLBACK_MODEL apontam para a GPU1, não para um modelo velho."""
    texto = MODELS_ENV.read_text(encoding="utf-8")
    divergentes = [
        (chave, valor)
        for chave, valor in re.findall(r"^(\w*FALLBACK_MODEL)=(\S+)\s*$", texto, re.MULTILINE)
        if valor.endswith(":gpu1") and valor != modelo_gpu1
    ]
    assert not divergentes, (
        "fallback aponta para modelo de GPU1 diferente de "
        f"{modelo_gpu1!r}: {divergentes}"
    )


def _modelos_do_models_env() -> dict[str, str]:
    """Todas as chaves *_MODEL declaradas em models.env."""
    texto = MODELS_ENV.read_text(encoding="utf-8")
    return dict(re.findall(r"^(\w*_MODEL)=(\S+)\s*$", texto, re.MULTILINE))


def test_dropins_systemd_nao_contradizem_models_env() -> None:
    """Drop-in não pode fixar um *_MODEL com valor diferente do models.env.

    Verifica a chave INTEIRA, não só valores ':gpu1'. Uma versão anterior deste
    teste só comparava sufixo ':gpu1' e por isso deixou passar um drop-in que
    mandava OLLAMA_PLAN_MODEL para a GPU1 enquanto o models.env (e a produção)
    diziam 'trading-analyst' — trocava a GPU de destino do plano sem ninguém ver.
    """
    canonico = _modelos_do_models_env()
    assert canonico, "nenhuma chave *_MODEL encontrada em models.env"

    ofensores: list[str] = []
    for conf in (RAIZ / "systemd").rglob("*.conf"):
        for linha_num, linha in enumerate(conf.read_text(encoding="utf-8").splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue
            match = re.match(r"\s*Environment=(\w*_MODEL)=(\S+)\s*$", linha)
            if not match:
                continue
            chave, valor = match.groups()
            esperado = canonico.get(chave)
            if esperado is not None and valor != esperado:
                ofensores.append(
                    f"{conf.relative_to(RAIZ)}:{linha_num} → {chave}={valor} "
                    f"(models.env diz {esperado})"
                )
    assert not ofensores, (
        "drop-in systemd contradiz deploy/crypto-agent/models.env:\n  "
        + "\n  ".join(ofensores)
    )


def test_mcp_ollama_local_usa_o_modelo_da_gpu1(modelo_gpu1: str) -> None:
    """O MCP ollama-local não pode rotear a GPU1 para um modelo não residente."""
    mcp = json.loads((RAIZ / ".mcp.json").read_text(encoding="utf-8"))
    env = mcp["mcpServers"]["ollama-local"]["env"]
    assert env["LLM_GPU1_MODEL"] == modelo_gpu1, (
        f"LLM_GPU1_MODEL={env['LLM_GPU1_MODEL']!r} diverge de "
        f"{modelo_gpu1!r} (models.env)."
    )


def test_selfheal_conhece_o_modelo_da_gpu1(modelo_gpu1: str) -> None:
    """O selfheal precisa tratar o modelo da GPU1 como leve e repô-lo após limpeza."""
    fonte = (RAIZ / "tools" / "ollama_gpu_selfheal.py").read_text(encoding="utf-8")

    light = re.search(r"LIGHT_MODELS\s*=\s*\{([^}]*)\}", fonte)
    assert light, "LIGHT_MODELS não encontrado"
    assert modelo_gpu1 in light.group(1), (
        f"{modelo_gpu1!r} fora de LIGHT_MODELS — se for pinado no GPU0, "
        "o selfheal não detecta."
    )

    warmup = re.search(r'GPU1_WARMUP_MODEL\s*=\s*os\.environ\.get\(\s*"GPU1_WARMUP_MODEL"\s*,\s*"([^"]+)"', fonte)
    assert warmup, "GPU1_WARMUP_MODEL não encontrado"
    assert warmup.group(1) == modelo_gpu1, (
        f"GPU1_WARMUP_MODEL default={warmup.group(1)!r} diverge de {modelo_gpu1!r} — "
        "a limpeza reporia o modelo errado na GPU1."
    )
