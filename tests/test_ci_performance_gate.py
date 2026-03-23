import argparse
import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "ci_performance_gate.py"
_SPEC = importlib.util.spec_from_file_location("ci_performance_gate", _MODULE_PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)
evaluate_report = _MOD.evaluate_report


def _args(**overrides):
    base = dict(
        min_realized_pnl_delta=0.0,
        min_win_rate_sell_pp=0.0,
        min_exec_rate_sell_pp=0.0,
        min_v0_sells=0,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_evaluate_report_passes_when_metrics_above_threshold():
    report = {
        "delta": {
            "realized_pnl_usd_delta": 0.12,
            "win_rate_sell_pp": 1.5,
            "exec_rate_sell_pp": 0.8,
        },
        "v0": {"trades": {"sells": 3}},
    }
    issues = evaluate_report(report, _args(min_v0_sells=1))
    assert issues == []


def test_evaluate_report_flags_all_regressions():
    report = {
        "delta": {
            "realized_pnl_usd_delta": -0.01,
            "win_rate_sell_pp": -2.0,
            "exec_rate_sell_pp": -0.5,
        },
        "v0": {"trades": {"sells": 0}},
    }
    issues = evaluate_report(report, _args(min_v0_sells=1))
    assert len(issues) == 4
    assert any("realized_pnl_usd_delta" in i for i in issues)
    assert any("win_rate_sell_pp" in i for i in issues)
    assert any("exec_rate_sell_pp" in i for i in issues)
    assert any("v0_sells" in i for i in issues)
