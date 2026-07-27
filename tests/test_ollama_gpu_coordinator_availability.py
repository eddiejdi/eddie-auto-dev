"""Elegibilidade por catálogo de modelos no ollama-gpu-coordinator.

Contexto: o coordenador roteava por score sem saber quais modelos cada endpoint
POSSUI — só sabia o que estava residente em VRAM (/api/ps). Resultado medido em
2026-07-27: 116 requisições de `trading-analyst` em 2 dias foram roteadas para a
NAS, que não tem esse modelo, e morreram com 404 (2,6% do tráfego do modelo).

Estes testes fixam as duas metades do contrato:
  - filtrar quando se SABE que o endpoint não tem o modelo;
  - não filtrar quando o catálogo é desconhecido (fail-open), para que um
    /api/tags intermitente nunca tire uma GPU do pool.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ollama_gpu_coordinator as coord  # noqa: E402


def _endpoint(name="gpu-test", host="http://127.0.0.1:9", vram=8192, priority=0):
    return coord.EndpointState(name=name, host=host, vram_total_mb=vram, priority=priority)


def _make_healthy(ep, available=None, loaded=None):
    """Coloca o endpoint em estado saudável sem tocar a rede."""
    import time

    ep._healthy = True
    ep._last_ok_poll = time.monotonic()
    ep._loaded = dict(loaded or {})
    if available is not None:
        ep._available = set(available)
        ep._available_known = True
    return ep


# ── fail-open ────────────────────────────────────────────────────────────────

def test_catalogo_desconhecido_nao_filtra():
    """Sem catálogo, tudo é elegível — não podemos quebrar roteamento que funciona."""
    ep = _make_healthy(_endpoint())
    assert ep._available_known is False
    assert ep.has_model_available("trading-analyst") is True
    assert ep.score("trading-analyst") < float("inf")


def test_tags_falhando_preserva_catalogo_anterior():
    ep = _make_healthy(_endpoint(), available={"trading-analyst:latest"})
    ep.host = "http://127.0.0.1:1"  # porta fechada → urlopen falha
    ep._poll_tags()
    assert ep._available_known is True
    assert ep.has_model_available("trading-analyst") is True


def test_tags_vazio_preserva_catalogo_anterior(monkeypatch):
    ep = _make_healthy(_endpoint(), available={"trading-analyst:latest"})

    class _Resp:
        def read(self):
            return b'{"models": []}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(coord.urllib.request, "urlopen", lambda *a, **k: _Resp())
    ep._poll_tags()
    assert ep.has_model_available("trading-analyst") is True


# ── filtragem com conhecimento positivo ──────────────────────────────────────

def test_modelo_ausente_do_catalogo_e_inelegivel():
    """O caso real: NAS sem trading-analyst."""
    ep = _make_healthy(_endpoint("nas-rtx2060"), available={"phi4-mini:latest"})
    assert ep.has_model_available("trading-analyst") is False
    assert ep.score("trading-analyst") == float("inf")


def test_modelo_presente_no_catalogo_e_elegivel():
    ep = _make_healthy(_endpoint(), available={"trading-analyst:latest"})
    assert ep.has_model_available("trading-analyst") is True
    assert ep.score("trading-analyst") < float("inf")


@pytest.mark.parametrize(
    "consulta, catalogo, esperado",
    [
        ("trading-analyst", {"trading-analyst:latest"}, True),
        ("trading-analyst:latest", {"trading-analyst:latest"}, True),
        ("phi4-mini:nas", {"phi4-mini:nas"}, True),
        ("trading-analyst", {"phi4-mini:latest"}, False),
        ("gemma3:1b", {"phi4-mini:latest"}, False),
    ],
)
def test_normalizacao_de_tag(consulta, catalogo, esperado):
    ep = _make_healthy(_endpoint(), available=catalogo)
    assert ep.has_model_available(consulta) is esperado


def test_modelo_residente_conta_como_disponivel():
    """Se está em VRAM, existe — mesmo que o catálogo esteja desatualizado."""
    ep = _make_healthy(_endpoint(), available={"outro:latest"}, loaded={"recem-baixado:latest": 100.0})
    assert ep.has_model_available("recem-baixado") is True


# ── roteamento no cluster ────────────────────────────────────────────────────

def test_pick_evita_endpoint_sem_o_modelo():
    """Reproduz o bug: sem o filtro, a NAS vencia por ter mais VRAM livre."""
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"trading-analyst:latest"},
        loaded={"trading-analyst:latest": 6000.0},
    )
    nas = _make_healthy(
        _endpoint("nas-rtx2060", vram=8192, priority=1),
        available={"phi4-mini:latest"},
    )
    nas._active = 0
    gpu0._active = 5  # GPU0 ocupada — antes isso bastava para desviar para a NAS

    cluster = coord.GPUCluster([gpu0, nas])
    assert cluster.pick("trading-analyst") is gpu0


def test_pick_retorna_none_quando_ninguem_tem_o_modelo():
    """Melhor um 503 explícito do coordenador que um 404 silencioso do endpoint."""
    gpu0 = _make_healthy(_endpoint("gpu0-rtx3060"), available={"phi4-mini:latest"})
    nas = _make_healthy(_endpoint("nas-rtx2060"), available={"phi4-mini:latest"})
    cluster = coord.GPUCluster([gpu0, nas])
    assert cluster.pick("modelo-inexistente") is None


def test_pin_por_sufixo_continua_mandando_para_o_endpoint_pinado():
    """O pin é intenção explícita: avisa no log, mas não desvia."""
    nas = _make_healthy(_endpoint("nas-rtx2060"), available={"phi4-mini:nas"})
    gpu0 = _make_healthy(_endpoint("gpu0-rtx3060"), available={"tudo:latest"})
    cluster = coord.GPUCluster([gpu0, nas])
    assert cluster.pick("phi4-mini:nas") is nas
