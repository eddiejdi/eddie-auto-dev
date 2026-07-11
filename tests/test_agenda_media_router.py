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


def test_default_llm_chain_prioriza_gpu0_nas_gpu1() -> None:
    chain = router.default_llm_chain()

    assert [endpoint.name for endpoint in chain] == ["gpu0", "nas", "gpu1"]
    assert chain[0].host.endswith(":11434")
    assert chain[1].host.endswith(":11436")
    assert chain[2].host.endswith(":11435")


def test_resolve_media_plan_balanced_usa_piper_gpu() -> None:
    plan = router.resolve_media_plan(quality="balanced", llm_auto_route=True)

    assert plan.quality == "balanced"
    assert plan.tts.backend == "piper-gpu"
    assert plan.tts.piper_use_cuda is True
    assert len(plan.llm_endpoints) == 3


def test_resolve_media_plan_best_usa_kokoro_com_fallbacks() -> None:
    plan = router.resolve_media_plan(quality="best", llm_auto_route=True)
    fallbacks = router.tts_fallback_chain(plan.tts)

    assert plan.tts.backend == "kokoro-gpu0"
    assert fallbacks[0] == "kokoro-gpu0"
    assert "gemini-tts" in fallbacks
    assert "piper-gpu" in fallbacks


def test_resolve_media_plan_manual_llm_override() -> None:
    plan = router.resolve_media_plan(
        quality="fast",
        llm_auto_route=False,
        ollama_host="http://example:11434",
        ollama_model="custom:1b",
        ollama_fallback_models="alt:1b",
    )

    assert len(plan.llm_endpoints) == 1
    assert plan.llm_endpoints[0].host == "http://example:11434"
    assert plan.llm_endpoints[0].model == "custom:1b"
    assert plan.llm_endpoints[0].fallback_models == ("alt:1b",)