#!/usr/bin/env python3
"""Testes para isolamento do arquivo de modelo por symbol+profile."""

from __future__ import annotations

import sys
import importlib
from pathlib import Path
from types import SimpleNamespace


_BTC_DIR = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))

sys.modules.setdefault(
    "numpy",
    SimpleNamespace(
        ndarray=object,
        array=lambda values: values,
    ),
)
sys.modules.pop("fast_model", None)
fast_model = importlib.import_module("fast_model")


class _DummyQLearning:
    def __init__(self) -> None:
        self.loaded_paths: list[str] = []

    def load(self, path: Path) -> bool:
        self.loaded_paths.append(Path(path).name)
        return True

    def save(self, path: Path) -> bool:
        self.loaded_paths.append(Path(path).name)
        return True


def test_fast_model_prefers_profile_scoped_model(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fast_model, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(fast_model, "FastQLearning", _DummyQLearning)
    (tmp_path / "qmodel_BTC_USDT__aggressive.pkl").write_text("scoped")
    (tmp_path / "qmodel_BTC_USDT.pkl").write_text("legacy")

    model = fast_model.FastTradingModel("BTC-USDT", model_scope="BTC-USDT__aggressive")

    assert model.q_model.loaded_paths == ["qmodel_BTC_USDT__aggressive.pkl"]


def test_fast_model_falls_back_to_legacy_symbol_model(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fast_model, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(fast_model, "FastQLearning", _DummyQLearning)
    (tmp_path / "qmodel_BTC_USDT.pkl").write_text("legacy")

    model = fast_model.FastTradingModel("BTC-USDT", model_scope="BTC-USDT__conservative")

    assert model.q_model.loaded_paths == ["qmodel_BTC_USDT.pkl"]
