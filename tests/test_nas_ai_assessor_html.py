from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSESSOR_PATH = ROOT / "tools" / "homelab" / "nas_ai_assessor.py"

spec = importlib.util.spec_from_file_location("nas_ai_assessor", ASSESSOR_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_fallback_html_uses_volume_ready_for_drive_and_media_labels() -> None:
    metrics = {
        "drive_ready": -1.0,
        "medium_loaded": -1.0,
        "volume_ready": 1.0,
        "compression_enabled": -1.0,
        "buffer_occupancy_pct": 50.0,
        "tape_write_bps": 0.0,
        "flush_bps": 0.0,
        "write_timeouts_24h": 0.0,
        "fc_abort_events_24h": 0.0,
    }
    html = mod.fallback_html({"overall": "saudavel", "issues": [], "positives": []}, metrics)
    assert "Drive</strong><br>Pronto" in html
    assert "Mídia</strong><br>Carregada" in html
    assert "Compressão</strong><br>N/A" in html
