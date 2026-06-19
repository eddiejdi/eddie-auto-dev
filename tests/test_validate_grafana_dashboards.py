from __future__ import annotations

from tools.validate_grafana_dashboards import (
    _template_values,
    expand_prometheus_builtins,
    substitute_template_vars,
)


def test_substitute_template_vars_supports_common_formats() -> None:
    variables = {
        "coin": ["BTC-USDT"],
        "profile": ["aggressive", "shadow"],
        "source": [".*"],
    }

    assert substitute_template_vars("symbol = '$coin'", variables) == "symbol = 'BTC-USDT'"
    assert substitute_template_vars("profile ~* '^(${profile:pipe})$'", variables) == "profile ~* '^(aggressive|shadow)$'"
    assert substitute_template_vars("profile IN (${profile:sqlstring})", variables) == "profile IN ('aggressive','shadow')"
    assert substitute_template_vars("source ~ '${source:regex}'", variables) == "source ~ '.*'"


def test_template_values_normalize_all_and_defaults() -> None:
    dashboard = {
        "templating": {
            "list": [
                {
                    "name": "profile",
                    "current": {"value": ["aggressive", "shadow"]},
                },
                {
                    "name": "instance",
                    "current": {"value": "$__all"},
                },
            ]
        }
    }

    values = _template_values(dashboard)

    assert values["profile"] == ["aggressive", "shadow"]
    assert values["instance"] == [".*"]
    assert values["coin"] == ["BTC-USDT"]


def test_expand_prometheus_builtins_replaces_grafana_intervals() -> None:
    expr = "rate(foo_total[$__rate_interval]) + increase(bar_total[$__range]) + avg_over_time(baz[$__interval])"
    assert expand_prometheus_builtins(expr) == "rate(foo_total[5m]) + increase(bar_total[1h]) + avg_over_time(baz[5m])"
