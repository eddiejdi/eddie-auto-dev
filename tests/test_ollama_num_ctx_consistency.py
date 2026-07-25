"""Guarda o num_ctx único usado nas chamadas Ollama do trading agent.

Contexto (incidente 2026-07-24): as chamadas de trade window / trade controls
mandavam num_ctx=2048 enquanto o Modelfile do trading-analyst fixa 4096. Um
num_ctx divergente obriga o Ollama a subir um runner novo; com
OLLAMA_MAX_LOADED_MODELS=1 e KEEP_ALIVE prendendo o runner residente, esse
runner nunca é agendado e a request morre na fila devolvendo
503 "maximum pending requests exceeded" — com a GPU 100% ociosa.

O agente ficou com 94% das chamadas LLM em 503 e o sintoma se disfarça de
"GPU sobrecarregada", que é o diagnóstico errado. Estes testes falham se
alguém reintroduzir um literal divergente.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

AGENT_SRC = Path(__file__).resolve().parent.parent / "btc_trading_agent" / "trading_agent.py"


@pytest.fixture(scope="module")
def source() -> str:
    return AGENT_SRC.read_text(encoding="utf-8")


def test_constante_num_ctx_existe_e_bate_com_o_modelfile(source: str) -> None:
    """_OLLAMA_NUM_CTX tem que existir e valer 4096 (o num_ctx do Modelfile)."""
    match = re.search(r"^\s*_OLLAMA_NUM_CTX\s*=\s*(\d+)\s*$", source, re.MULTILINE)
    assert match, "_OLLAMA_NUM_CTX sumiu de trading_agent.py"
    assert int(match.group(1)) == 4096, (
        "_OLLAMA_NUM_CTX divergiu de 4096. Só mude junto com o "
        "'PARAMETER num_ctx' do Modelfile do modelo servido — divergir "
        "derruba o agente inteiro em 503."
    )


def test_nenhuma_chamada_usa_num_ctx_literal(source: str) -> None:
    """Todo num_ctx nas options tem que referenciar a constante, nunca um literal."""
    tree = ast.parse(source)
    literais: list[tuple[int, int]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for chave, valor in zip(node.keys, node.values):
            if not (isinstance(chave, ast.Constant) and chave.value == "num_ctx"):
                continue
            if isinstance(valor, ast.Constant) and isinstance(valor.value, int):
                literais.append((valor.lineno, valor.value))

    assert not literais, (
        "num_ctx literal encontrado em "
        + ", ".join(f"linha {ln} (={v})" for ln, v in literais)
        + ". Use self._OLLAMA_NUM_CTX — um valor divergente do Modelfile "
        "faz o Ollama devolver 503 'maximum pending requests exceeded'."
    )


def test_fallback_do_plano_herda_o_mesmo_num_ctx(source: str) -> None:
    """O fallback do plano (GPU1) não pode sobrescrever num_ctx.

    A GPU1 serve lfm2.5-fast:gpu1, que também é num_ctx 4096 desde 2026-07-10
    (substituiu o gemma3-fast, esse sim 2048). Sobrescrever aqui reintroduz o 503.
    """
    match = re.search(r"plan_options_fallback\s*=\s*\{([^}]*)\}", source)
    assert match, "plan_options_fallback não encontrado"
    assert "num_ctx" not in match.group(1), (
        "plan_options_fallback voltou a sobrescrever num_ctx. A GPU1 serve "
        "lfm2.5-fast:gpu1 com num_ctx 4096; um valor menor só gera 503."
    )
