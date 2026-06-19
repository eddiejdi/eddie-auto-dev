#!/usr/bin/env python3
"""Valida dashboards Grafana contra backends reais.

Suporta:
- Prometheus via /api/v1/query
- PostgreSQL via /api/ds/query do próprio Grafana

Uso:
  python3 tools/validate_grafana_dashboards.py grafana/dashboards/storj-node-monitor.json
  python3 tools/validate_grafana_dashboards.py monitoring/grafana/provisioning/dashboards --recursive
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_GRAFANA_URL = "http://localhost:3002"
DEFAULT_PROMETHEUS_URL = "http://localhost:9090"
DEFAULT_FROM_MS = 1_718_841_600_000
DEFAULT_TO_MS = 1_718_928_000_000

VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([A-Za-z_][A-Za-z0-9_]*))?\}|\$([A-Za-z_][A-Za-z0-9_]*)")
UNRESOLVED_PATTERN = re.compile(r"\$(?:\{[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)?\}|[A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class ValidationError:
    dashboard: str
    panel_id: int | str
    title: str
    ref_id: str
    datasource_uid: str
    query_type: str
    detail: str


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} não contém objeto JSON")
    if "dashboard" in data and isinstance(data["dashboard"], dict):
        return data["dashboard"]
    return data


def _iter_dashboard_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    pattern = "**/*.json" if recursive else "*.json"
    return sorted(candidate for candidate in path.glob(pattern) if candidate.is_file())


def _iter_panels(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    panels = dashboard.get("panels", [])
    if not isinstance(panels, list):
        return []
    flattened: list[dict[str, Any]] = []
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        flattened.append(panel)
        nested = panel.get("panels", [])
        if isinstance(nested, list):
            flattened.extend(item for item in nested if isinstance(item, dict))
    return flattened


def _normalize_values(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        values = [str(item) for item in raw if item not in (None, "")]
    else:
        values = [str(raw)] if raw != "" else []
    cleaned = [value for value in values if value not in ("$__all", "__all")]
    if any(value in (".*", "All", "all") for value in values):
        return [".*"]
    return cleaned


def _template_values(dashboard: dict[str, Any]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    templating = dashboard.get("templating", {})
    if not isinstance(templating, dict):
        return values
    variables = templating.get("list", [])
    if not isinstance(variables, list):
        return values
    for item in variables:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        current = item.get("current", {})
        if not isinstance(current, dict):
            current = {}
        normalized = _normalize_values(current.get("value"))
        if not normalized:
            options = item.get("options", [])
            if isinstance(options, list):
                for option in options:
                    if not isinstance(option, dict):
                        continue
                    normalized = _normalize_values(option.get("value"))
                    if normalized:
                        break
        if normalized:
            values[str(name)] = normalized
    values.setdefault("coin", ["BTC-USDT"])
    values.setdefault("profile", ["conservative"])
    values.setdefault("symbol", ["BTC-USDT"])
    values.setdefault("instance", [".*"])
    values.setdefault("source", [".*"])
    values.setdefault("target", [".*"])
    values.setdefault("category", [".*"])
    values.setdefault("provider", [".*"])
    values.setdefault("drive", [".*"])
    values.setdefault("message_type", [".*"])
    values.setdefault("tunnel", [".*"])
    return values


def _render_variable(values: list[str], fmt: str | None) -> str:
    fmt = fmt or "default"
    if not values:
        return ".*" if fmt in {"regex", "pipe"} else ""
    if fmt == "regex":
        if values == [".*"]:
            return ".*"
        return "|".join(re.escape(value) for value in values)
    if fmt == "pipe":
        return ".*" if values == [".*"] else "|".join(values)
    if fmt in {"sqlstring", "singlequote"}:
        if values == [".*"]:
            return "'aggressive','conservative','shadow'"
        return ",".join("'" + value.replace("'", "''") + "'" for value in values)
    if fmt == "raw":
        return values[0]
    return values[0]


def substitute_template_vars(text: str, variables: dict[str, list[str]]) -> str:
    def repl(match: re.Match[str]) -> str:
        braced_name = match.group(1)
        braced_fmt = match.group(2)
        plain_name = match.group(3)
        name = braced_name or plain_name or ""
        if name.startswith("__"):
            return match.group(0)
        return _render_variable(variables.get(name, []), braced_fmt)

    return VARIABLE_PATTERN.sub(repl, text)


def expand_prometheus_builtins(text: str) -> str:
    replacements = {
        "$__interval": "5m",
        "${__interval}": "5m",
        "$__rate_interval": "5m",
        "${__rate_interval}": "5m",
        "$__range": "1h",
        "${__range}": "1h",
    }
    for needle, value in replacements.items():
        text = text.replace(needle, value)
    return text


def _find_unresolved_user_variable(text: str) -> str | None:
    for match in UNRESOLVED_PATTERN.finditer(text):
        token = match.group(0)
        if token.startswith("$__") or token.startswith("${__"):
            continue
        return token
    return None


def _auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: Any | None = None) -> dict[str, Any]:
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=payload, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def validate_prometheus(expr: str, prometheus_url: str) -> str | None:
    query = urllib.parse.urlencode({"query": expr})
    url = f"{prometheus_url.rstrip('/')}/api/v1/query?{query}"
    try:
        data = _http_json(url)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        return f"HTTP {exc.code}: {body[:500]}"
    if data.get("status") != "success":
        return json.dumps(data, ensure_ascii=False)
    return None


def validate_sql(
    raw_sql: str,
    datasource: dict[str, str],
    grafana_url: str,
    grafana_user: str,
    grafana_pass: str,
    from_ms: int,
    to_ms: int,
) -> str | None:
    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {
                    "uid": datasource.get("uid", ""),
                    "type": datasource.get("type", ""),
                },
                "rawSql": raw_sql,
                "format": "table",
            }
        ],
        "from": str(from_ms),
        "to": str(to_ms),
    }
    headers = {
        "Authorization": _auth_header(grafana_user, grafana_pass),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{grafana_url.rstrip('/')}/api/ds/query"
    try:
        data = _http_json(url, method="POST", headers=headers, body=payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        return f"HTTP {exc.code}: {body[:500]}"
    result = data.get("results", {}).get("A", {})
    if result.get("error"):
        return str(result["error"])
    if result.get("status") not in (200, "success", None):
        return json.dumps(result, ensure_ascii=False)
    return None


def validate_dashboard_file(
    path: Path,
    *,
    prometheus_url: str,
    grafana_url: str,
    grafana_user: str,
    grafana_pass: str,
    from_ms: int,
    to_ms: int,
) -> list[ValidationError]:
    dashboard = _load_json(path)
    variables = _template_values(dashboard)
    errors: list[ValidationError] = []

    for panel in _iter_panels(dashboard):
        targets = panel.get("targets", [])
        if not isinstance(targets, list):
            continue
        datasource = panel.get("datasource")
        panel_datasource = datasource if isinstance(datasource, dict) else {}
        panel_id = panel.get("id", "?")
        title = str(panel.get("title", "?"))
        for target in targets:
            if not isinstance(target, dict):
                continue
            target_datasource = target.get("datasource")
            datasource_info = target_datasource if isinstance(target_datasource, dict) else panel_datasource
            ds_uid = str(datasource_info.get("uid", ""))
            ds_type = str(datasource_info.get("type", ""))
            ref_id = str(target.get("refId", "?"))
            expr = target.get("expr")
            raw_sql = target.get("rawSql")

            if expr:
                rendered = substitute_template_vars(str(expr), variables)
                rendered = expand_prometheus_builtins(rendered)
                unresolved = _find_unresolved_user_variable(rendered)
                if unresolved:
                    errors.append(
                        ValidationError(path.name, panel_id, title, ref_id, ds_uid, "promql", f"variável não resolvida: {unresolved}")
                    )
                    continue
                detail = validate_prometheus(rendered, prometheus_url)
                if detail:
                    errors.append(ValidationError(path.name, panel_id, title, ref_id, ds_uid, "promql", detail))
                continue

            if raw_sql:
                rendered = substitute_template_vars(str(raw_sql), variables)
                unresolved = _find_unresolved_user_variable(rendered)
                if unresolved:
                    errors.append(
                        ValidationError(path.name, panel_id, title, ref_id, ds_uid, "sql", f"variável não resolvida: {unresolved}")
                    )
                    continue
                detail = validate_sql(
                    rendered,
                    {"uid": ds_uid, "type": ds_type},
                    grafana_url,
                    grafana_user,
                    grafana_pass,
                    from_ms,
                    to_ms,
                )
                if detail:
                    errors.append(ValidationError(path.name, panel_id, title, ref_id, ds_uid, "sql", detail))
    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Valida dashboards Grafana contra Prometheus e Grafana SQL API")
    parser.add_argument("path", help="Arquivo JSON ou diretório de dashboards")
    parser.add_argument("--recursive", action="store_true", help="Varre subdiretórios quando path for diretório")
    parser.add_argument("--prometheus-url", default=DEFAULT_PROMETHEUS_URL)
    parser.add_argument("--grafana-url", default=DEFAULT_GRAFANA_URL)
    parser.add_argument("--grafana-user", default="admin")
    parser.add_argument("--grafana-pass", default="")
    parser.add_argument("--from-ms", type=int, default=DEFAULT_FROM_MS)
    parser.add_argument("--to-ms", type=int, default=DEFAULT_TO_MS)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    path = Path(args.path)
    files = _iter_dashboard_files(path, args.recursive)
    if not files:
        print(f"Nenhum dashboard encontrado em {path}", file=sys.stderr)
        return 1

    all_errors: list[ValidationError] = []
    validated = 0
    for file_path in files:
        dashboard = _load_json(file_path)
        if not dashboard.get("uid"):
            continue
        validated += 1
        all_errors.extend(
            validate_dashboard_file(
                file_path,
                prometheus_url=args.prometheus_url,
                grafana_url=args.grafana_url,
                grafana_user=args.grafana_user,
                grafana_pass=args.grafana_pass,
                from_ms=args.from_ms,
                to_ms=args.to_ms,
            )
        )

    if all_errors:
        for error in all_errors:
            print(
                f"[FAIL] {error.dashboard} panel={error.panel_id} ref={error.ref_id} "
                f"type={error.query_type} ds={error.datasource_uid} title={error.title} :: {error.detail}"
            )
        print(f"Dashboards validados: {validated} | falhas: {len(all_errors)}", file=sys.stderr)
        return 1

    print(f"Dashboards validados: {validated} | falhas: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
