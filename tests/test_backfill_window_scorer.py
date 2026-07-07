"""Testes do scorer contrafactual do backfill de window (Fase 2)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "backfill_window",
    Path(__file__).resolve().parent.parent / "scripts" / "trading_analyst_backfill_window_dataset.py",
)


@pytest.fixture(scope="module")
def mod():
    # Stub do training_db para não exigir psycopg2/DSN ao importar o script.
    import sys
    import types

    fake = types.ModuleType("training_db")
    fake.TrainingDatabase = object  # type: ignore[attr-defined]
    sys.modules.setdefault("training_db", fake)
    module = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(module)
    return module


def score(mod, bars, entry_low=100.0, entry_high=101.0, target_sell=103.0, stop_pct=0.02):
    return mod.score_price_path(bars, entry_low, entry_high, target_sell, stop_pct)


def test_win_target_before_stop(mod):
    # Entra (low toca 101), depois sobe até o target 103 sem furar stop (~98.98).
    bars = [(101.5, 100.8, 101.0), (102.0, 101.0, 101.8), (103.5, 102.0, 103.2)]
    label, detail = score(mod, bars)
    assert label == "win"
    assert detail["exit"] == "target"


def test_loss_stop_before_target(mod):
    # Entra e cai furando o stop (101*0.98 = 98.98) antes de qualquer target.
    bars = [(101.2, 100.5, 100.8), (100.0, 98.5, 98.7)]
    label, detail = score(mod, bars)
    assert label == "loss"
    assert detail["exit"] == "stop"


def test_no_entry_when_band_never_touched(mod):
    # Preço fica sempre acima de entry_high=101 → nunca enche.
    bars = [(105.0, 102.0, 104.0), (106.0, 103.0, 105.0)]
    label, _ = score(mod, bars)
    assert label == "no_entry"


def test_timeout_flat_positive(mod):
    # Entra, não bate target nem stop; fecha acima do fill (101) → flat_pos.
    bars = [(101.5, 100.9, 101.0), (102.2, 101.0, 102.0)]
    label, detail = score(mod, bars)
    assert label == "flat_pos"
    assert detail["exit"] == "timeout"


def test_timeout_flat_negative(mod):
    # Entra a 101, oscila sem furar stop, fecha abaixo do fill → flat_neg.
    bars = [(101.5, 100.9, 101.0), (101.2, 99.5, 100.2)]
    label, detail = score(mod, bars)
    assert label == "flat_neg"
    assert detail["exit"] == "timeout"


def test_same_bar_target_and_stop_is_conservative_loss(mod):
    # Bar único toca target (103) e stop (98.98) → assume loss.
    bars = [(103.5, 98.0, 100.0)]
    label, detail = score(mod, bars)
    assert label == "loss"
    assert detail["exit"] == "stop_and_target_same_bar"


def test_invalid_inputs(mod):
    assert score(mod, [], )[0] == "invalid"
    # target abaixo da entrada → degenerada
    assert score(mod, [(101.0, 100.0, 100.5)], target_sell=100.5)[0] == "invalid"


def test_positive_labels_constant(mod):
    assert mod.POSITIVE_LABELS == ("win", "flat_pos")


def test_is_positive_win_always_kept(mod):
    assert mod.is_positive_example("win", {"pnl_pct": 0.0}, min_flat_pnl=0.15) is True


def test_is_positive_flat_pos_respects_floor(mod):
    # flat_pos acima do piso conta; abaixo é descartado.
    assert mod.is_positive_example("flat_pos", {"pnl_pct": 0.20}, min_flat_pnl=0.15) is True
    assert mod.is_positive_example("flat_pos", {"pnl_pct": 0.05}, min_flat_pnl=0.15) is False


def test_is_positive_negatives_never_kept(mod):
    for lbl in ("loss", "flat_neg", "no_entry", "invalid"):
        assert mod.is_positive_example(lbl, {"pnl_pct": 99.0}, min_flat_pnl=0.0) is False


def test_shadow_has_window_settings(mod):
    assert "shadow" in mod.WINDOW_SETTINGS


def test_build_target_is_sorted_json(mod):
    w = {"entry_low": 100.126, "entry_high": 101.44, "target_sell": 103.9,
         "min_confidence": 0.6123, "min_trade_interval": 120, "ttl_seconds": 60}
    out = mod.build_target(w)
    assert out == (
        '{"entry_high": 101.44, "entry_low": 100.13, "min_confidence": 0.612, '
        '"min_trade_interval": 120, "target_sell": 103.9, "ttl_seconds": 60}'
    )
