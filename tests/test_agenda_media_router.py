from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
MODULE_PATH = TOOLS_DIR / "agenda_media_router.py"
sys.path.insert(0, str(TOOLS_DIR))

_SPEC = importlib.util.spec_from_file_location("agenda_media_router", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
router = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = router
_SPEC.loader.exec_module(router)


def test_default_llm_chain_usa_apenas_coordinator() -> None:
    chain = router.default_llm_chain()

    assert len(chain) == 1
    assert chain[0].name == "coordinator"
    assert chain[0].host.endswith(":11437")
    assert router.is_coordinator_host(chain[0].host)
    assert not router.is_direct_ollama_host(chain[0].host)
    # Modelos leves multi-GPU (sem prisão exclusiva em :gpu1)
    assert "gemma" in chain[0].model or chain[0].model.endswith(":gpu1")
    assert "llama3.2:3b" not in chain[0].fallback_models
    # Fallbacks cobrem NAS + soft-pin gpu1
    joined = ",".join(chain[0].fallback_models)
    assert "phi4-mini" in joined


def test_distributed_llm_chain_espalha_primarios() -> None:
    chain = router.distributed_llm_chain()
    assert len(chain) >= 3
    assert all(ep.host.endswith(":11437") for ep in chain)
    models = {ep.model for ep in chain}
    # Agenda: GPU1 + NAS — nunca família trading
    assert all(not m.lower().startswith("trading") for m in models)
    for ep in chain:
        assert all(not fb.lower().startswith("trading") for fb in ep.fallback_models)
    assert any(m.endswith(":gpu1") or "gemma" in m or "lfm" in m for m in models)
    assert any("phi4" in m or m.endswith(":nas") for m in models)


def test_resolve_media_plan_auto_usa_cadeia_distribuida(monkeypatch) -> None:
    monkeypatch.setenv("AGENDA_LLM_DISTRIBUTE", "1")
    plan = router.resolve_media_plan(quality="fast", llm_auto_route=True)
    assert len(plan.llm_endpoints) >= 3
    assert all(ep.host.endswith(":11437") for ep in plan.llm_endpoints)


def test_ensure_coordinator_host_remapeia_gpus_diretas() -> None:
    assert router.ensure_coordinator_host("http://192.168.15.2:11434").endswith(":11437")
    assert router.ensure_coordinator_host("http://192.168.15.2:11435").endswith(":11437")
    assert router.ensure_coordinator_host("http://192.168.15.4:11436").endswith(":11437")
    assert router.ensure_coordinator_host("http://192.168.15.2:11437") == "http://192.168.15.2:11437"


def test_resolve_media_plan_balanced_usa_piper_gpu() -> None:
    plan = router.resolve_media_plan(quality="balanced", llm_auto_route=True)

    assert plan.quality == "balanced"
    assert plan.tts.backend == "piper-gpu"
    assert plan.tts.piper_use_cuda is True
    # Cadeia distribuída: várias entradas no coordinator (GPU0/GPU1/NAS)
    assert len(plan.llm_endpoints) >= 1
    assert all(ep.host.endswith(":11437") for ep in plan.llm_endpoints)


def test_resolve_media_plan_best_usa_kokoro_com_fallbacks() -> None:
    plan = router.resolve_media_plan(quality="best", llm_auto_route=True)
    fallbacks = router.tts_fallback_chain(plan.tts)

    assert plan.tts.backend == "kokoro-gpu0"
    assert fallbacks[0] == "kokoro-gpu0"
    assert "gemini-tts" in fallbacks
    assert "piper-gpu" in fallbacks


def test_resolve_media_plan_manual_llm_override_remapeia_para_coordinator() -> None:
    plan = router.resolve_media_plan(
        quality="fast",
        llm_auto_route=False,
        ollama_host="http://example:11434",
        ollama_model="custom:1b",
        ollama_fallback_models="alt:1b",
    )

    assert len(plan.llm_endpoints) == 1
    # Override com porta direta e remapeado para coordinator (politica obrigatoria)
    assert plan.llm_endpoints[0].host == "http://example:11437"
    assert plan.llm_endpoints[0].model == "custom:1b"
    assert plan.llm_endpoints[0].fallback_models == ("alt:1b",)


def test_resolve_media_plan_allow_direct_ollama_diagnostico() -> None:
    plan = router.resolve_media_plan(
        quality="fast",
        llm_auto_route=False,
        ollama_host="http://example:11434",
        ollama_model="custom:1b",
        allow_direct_ollama=True,
    )

    assert plan.llm_endpoints[0].host == "http://example:11434"
