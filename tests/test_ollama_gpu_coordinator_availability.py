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
    """Pin livre: endpoint preferido quando saudável e sem carga."""
    nas = _make_healthy(_endpoint("nas-rtx2060"), available={"phi4-mini:nas"})
    gpu0 = _make_healthy(_endpoint("gpu0-rtx3060"), available={"tudo:latest", "phi4-mini:nas"})
    cluster = coord.GPUCluster([gpu0, nas])
    assert cluster.pick("phi4-mini:nas") is nas


def test_soft_pin_spill_quando_pinado_ocupado(monkeypatch):
    """Soft-pin: GPU pinada busy → least-load em outra (NAS), NÃO na GPU0 trading."""
    monkeypatch.setattr(coord, "SOFT_PIN", True)
    monkeypatch.setattr(coord, "SOFT_PIN_BUSY_THRESHOLD", 1)
    monkeypatch.setattr(coord, "TRADING_EXCLUSIVE_GPU0", True)
    monkeypatch.setattr(coord, "TRADING_RESERVE_GPU0", True)
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"gemma3-fast:gpu1"},
        loaded={"gemma3-fast:gpu1": 900.0},
    )
    gpu1._active = 2  # ocupada
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"gemma3-fast:gpu1", "gemma3:1b", "trading-analyst:latest"},
        loaded={"trading-analyst:latest": 6500.0},
    )
    gpu0._active = 0
    nas = _make_healthy(
        _endpoint("nas-rtx2060", vram=8192, priority=1),
        available={"gemma3-fast:gpu1"},
    )
    nas._active = 0
    cluster = coord.GPUCluster([gpu0, gpu1, nas])
    picked = cluster.pick("gemma3-fast:gpu1")
    assert picked is nas  # spill para NAS, nunca para casa do trading


def test_soft_pin_livre_prefere_endpoint_pinado(monkeypatch):
    monkeypatch.setattr(coord, "SOFT_PIN", True)
    monkeypatch.setattr(coord, "SOFT_PIN_BUSY_THRESHOLD", 1)
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"gemma3-fast:gpu1"},
    )
    gpu1._active = 0
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"gemma3-fast:gpu1"},
    )
    cluster = coord.GPUCluster([gpu0, gpu1])
    assert cluster.pick("gemma3-fast:gpu1") is gpu1


def test_hard_pin_sem_spill_quando_soft_pin_off(monkeypatch):
    monkeypatch.setattr(coord, "SOFT_PIN", False)
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"gemma3-fast:gpu1"},
    )
    gpu1._healthy = False  # pinado caído
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"gemma3-fast:gpu1"},
    )
    cluster = coord.GPUCluster([gpu0, gpu1])
    assert cluster.pick("gemma3-fast:gpu1") is None


def test_least_load_distribui_modelo_sem_pin():
    """Modelo sem sufixo: endpoint livre vence o ocupado."""
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"gemma3:1b"},
        loaded={"trading-analyst:latest": 6000.0},
    )
    gpu0._active = 3
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"gemma3:1b"},
    )
    gpu1._active = 0
    nas = _make_healthy(
        _endpoint("nas-rtx2060", vram=8192, priority=1),
        available={"phi4-mini:latest"},
    )
    cluster = coord.GPUCluster([gpu0, gpu1, nas])
    # Com trading residente, GPU0 está reservada — gemma vai para GPU1
    assert cluster.pick("gemma3:1b") is gpu1


def test_gpu0_exclusiva_recusa_auxiliar_por_default(monkeypatch):
    """Com TRADING_EXCLUSIVE_GPU0, auxiliar NÃO usa a 3060 (protege trading)."""
    monkeypatch.setattr(coord, "TRADING_RESERVE_GPU0", True)
    monkeypatch.setattr(coord, "TRADING_EXCLUSIVE_GPU0", True)
    monkeypatch.setattr(coord, "AUX_MAX_VRAM_MB", 1800)
    monkeypatch.setattr(coord, "TRADING_HEADROOM_MB", 1024)
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"gemma3:1b", "trading-analyst:latest", "mistral:7b"},
        loaded={"trading-analyst:latest": 6500.0},
    )
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"gemma3:1b", "mistral:7b"},
    )
    gpu1._active = 3
    cluster = coord.GPUCluster([gpu0, gpu1])
    # Auxiliar não invade a 3060
    assert cluster.pick("gemma3:1b") is gpu1
    assert cluster.pick("trading-analyst:latest") is gpu0
    assert cluster.pick("trading-analyst") is gpu0


def test_gpu0_aceita_auxiliar_pequeno_se_exclusive_off(monkeypatch):
    """Com EXCLUSIVE=0, auxiliar ~1B ainda pode usar VRAM livre da 3060."""
    monkeypatch.setattr(coord, "TRADING_RESERVE_GPU0", True)
    monkeypatch.setattr(coord, "TRADING_EXCLUSIVE_GPU0", False)
    monkeypatch.setattr(coord, "AUX_MAX_VRAM_MB", 1800)
    monkeypatch.setattr(coord, "TRADING_HEADROOM_MB", 1024)
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"gemma3:1b", "trading-analyst:latest", "mistral:7b"},
        loaded={"trading-analyst:latest": 6500.0},  # free ≈ 5788 MB
    )
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"gemma3:1b", "mistral:7b"},
    )
    gpu1._active = 3
    cluster = coord.GPUCluster([gpu0, gpu1])
    assert cluster.pick("gemma3:1b") is gpu0
    assert cluster.pick("trading-analyst") is gpu0


def test_gpu0_recusa_modelo_grande_com_trading_residente(monkeypatch):
    monkeypatch.setattr(coord, "TRADING_RESERVE_GPU0", True)
    monkeypatch.setattr(coord, "AUX_MAX_VRAM_MB", 1800)
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"mistral:7b", "trading-analyst:latest", "gemma3:1b"},
        loaded={"trading-analyst:latest": 6500.0},
    )
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"mistral:7b"},  # 7B não cabe na 1050 na prática, mas catálogo
    )
    nas = _make_healthy(
        _endpoint("nas-rtx2060", vram=8192, priority=1),
        available={"mistral:7b", "phi4-mini:latest"},
    )
    cluster = coord.GPUCluster([gpu0, gpu1, nas])
    picked = cluster.pick("mistral:7b")
    assert picked is not gpu0
    assert picked in (gpu1, nas)


def test_gpu0_recusa_auxiliar_sem_headroom(monkeypatch):
    """Livre insuficiente para modelo + headroom → não usa a 3060."""
    monkeypatch.setattr(coord, "TRADING_RESERVE_GPU0", True)
    monkeypatch.setattr(coord, "AUX_MAX_VRAM_MB", 1800)
    monkeypatch.setattr(coord, "TRADING_HEADROOM_MB", 1024)
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        available={"gemma3:1b", "trading-analyst:latest"},
        # free = 12288-11500 = 788 < 900*1.1+1024
        loaded={"trading-analyst:latest": 11500.0},
    )
    gpu1 = _make_healthy(
        _endpoint("gpu1-gtx1050", vram=2048, priority=2),
        available={"gemma3:1b"},
    )
    cluster = coord.GPUCluster([gpu0, gpu1])
    assert cluster.pick("gemma3:1b") is gpu1


def test_is_small_auxiliary_model():
    assert coord.is_small_auxiliary_model("gemma3:1b")
    assert coord.is_small_auxiliary_model("llama3.2:1b")
    assert coord.is_small_auxiliary_model("lfm2.5-fast:gpu1")
    assert not coord.is_small_auxiliary_model("mistral:7b")
    assert not coord.is_small_auxiliary_model("llama3.1:8b")
    assert not coord.is_small_auxiliary_model("trading-analyst:latest")


def test_trading_nunca_entra_em_evictable():
    gpu0 = _make_healthy(
        _endpoint("gpu0-rtx3060", vram=12288, priority=0),
        loaded={
            "trading-analyst:latest": 6500.0,
            "gemma3:1b": 900.0,
        },
    )
    names = [n for _, n in gpu0.evictable_models()]
    assert "trading-analyst:latest" not in names
    assert "gemma3:1b" in names


def test_unload_recusa_modelo_protegido(monkeypatch):
    calls = []

    def _fake_urlopen(*a, **k):
        calls.append(True)
        raise AssertionError("não deveria chamar rede para evict de trading")

    monkeypatch.setattr(coord.urllib.request, "urlopen", _fake_urlopen)
    cluster = coord.GPUCluster([])
    ep = _make_healthy(_endpoint("gpu0-rtx3060"), loaded={"trading-analyst:latest": 6500.0})
    cluster._unload_model(ep, "trading-analyst:latest")
    assert calls == []


def test_is_protected_model_familia_trading():
    assert coord.is_protected_model("trading-analyst:latest")
    assert coord.is_protected_model("trading-analyst-phi4:latest")
    assert coord.is_protected_model("trading-sentiment:latest")
    assert coord.is_protected_model("trading-analyst-candidate")
    assert not coord.is_protected_model("gemma3:1b")
    assert not coord.is_protected_model("eddie-persona-safe")
