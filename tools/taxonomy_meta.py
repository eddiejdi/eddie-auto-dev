#!/usr/bin/env python3
"""
Metadados compartilhados da taxonomia expandida:
  - ownership (serviço / time)
  - lifecycle status (active | deprecated | unused | experimental)
  - links explícitos API ↔ table (anotações e OpenAPI x-tables)
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ownership registry: path fragment → owner id + team
# Ordem: mais específico primeiro.
# ---------------------------------------------------------------------------
OWNER_RULES: list[tuple[str, dict[str, str]]] = [
    ("btc_trading_agent", {"owner": "btc_trading_agent", "team": "trading"}),
    ("clear_trading_agent", {"owner": "clear_trading_agent", "team": "trading"}),
    ("mt5_bridge", {"owner": "mt5_bridge", "team": "trading"}),
    ("marketing", {"owner": "marketing", "team": "growth"}),
    ("secrets_agent", {"owner": "secrets_agent", "team": "security"}),
    ("authentik", {"owner": "authentik", "team": "security"}),
    ("nextcloud", {"owner": "nextcloud", "team": "storage"}),
    ("tape_", {"owner": "tape", "team": "storage"}),
    ("ltfs", {"owner": "ltfs", "team": "storage"}),
    ("storage_portal", {"owner": "storage_portal", "team": "storage"}),
    ("wiki_agent", {"owner": "wiki", "team": "knowledge"}),
    ("wiki", {"owner": "wiki", "team": "knowledge"}),
    ("cmdb", {"owner": "cmdb", "team": "infra"}),
    ("banking", {"owner": "banking", "team": "finance"}),
    ("belvo", {"owner": "banking", "team": "finance"}),
    ("x_agent", {"owner": "x_agent", "team": "social"}),
    ("agent_communication", {"owner": "agent_bus", "team": "platform"}),
    ("operation_agent", {"owner": "operation_agent", "team": "platform"}),
    ("meeting_translator", {"owner": "meeting_translator", "team": "productivity"}),
    ("conube", {"owner": "conube", "team": "ops"}),
    ("huggingface", {"owner": "huggingface", "team": "llm"}),
    ("bn_acervo", {"owner": "bn_acervo", "team": "content"}),
    ("code_runner", {"owner": "code_runner", "team": "platform"}),
    ("ssh_agent", {"owner": "ssh_agent", "team": "infra"}),
    ("grafana", {"owner": "grafana", "team": "observability"}),
    ("tools/migrations", {"owner": "platform", "team": "platform"}),
    ("tools/agent_ipc", {"owner": "agent_bus", "team": "platform"}),
    ("specialized_agents/api", {"owner": "api_server", "team": "platform"}),
    ("content_automation", {"owner": "content_automation", "team": "content"}),
    ("user_management", {"owner": "user_management", "team": "identity"}),
    ("home_", {"owner": "home_automation", "team": "iot"}),
    ("setup_grafana_home", {"owner": "home_automation", "team": "iot"}),
]

# Schema → owner default when path is weak
SCHEMA_OWNERS: dict[str, dict[str, str]] = {
    "btc": {"owner": "btc_trading_agent", "team": "trading"},
    "clear": {"owner": "clear_trading_agent", "team": "trading"},
    "marketing": {"owner": "marketing", "team": "growth"},
}

VALID_STATUSES = frozenset(
    {"active", "deprecated", "unused", "experimental"}
)

# Explicit annotation patterns
# taxonomy: status=deprecated owner=foo tables=btc.trades,btc.candles
TAXONOMY_META_RE = re.compile(
    r"""taxonomy:\s*
        ((?:status|owner|team|tables|table)\s*=\s*[^;\n]+(?:\s*;\s*)?)+
    """,
    re.IGNORECASE | re.VERBOSE,
)
TAXONOMY_KV_RE = re.compile(
    r"(status|owner|team|tables|table)\s*=\s*([^;\n]+)",
    re.IGNORECASE,
)
# Shorthand: tables: btc.trades  OR  # tables=btc.trades
# Note: avoid bare # in VERBOSE mode (starts a comment) — use character class.
TABLES_SHORTHAND_RE = re.compile(
    r"(?:[#]|//|--)\s*(?:taxonomy:\s*)?tables?\s*[:=]\s*(?P<tables>[A-Za-z0-9_.,\s]+)",
    re.IGNORECASE,
)
DEPRECATED_MARKER_RE = re.compile(
    r"(?:@deprecated\b|deprecated\s*=\s*True|taxonomy:\s*[^\n]*status\s*=\s*deprecated)",
    re.IGNORECASE,
)
EXPERIMENTAL_MARKER_RE = re.compile(
    r"(?:taxonomy:\s*[^\n]*status\s*=\s*experimental|@experimental\b)",
    re.IGNORECASE,
)


def resolve_owner_from_path(path: str | Path, schema: str | None = None) -> dict[str, str]:
    """Return {owner, team} from file path and optional DB schema."""
    rel = str(path).replace("\\", "/")
    for fragment, meta in OWNER_RULES:
        if fragment in rel:
            return dict(meta)
    if schema and schema.lower() in SCHEMA_OWNERS:
        return dict(SCHEMA_OWNERS[schema.lower()])
    # fallback: first path component
    parts = [p for p in Path(rel).parts if p not in {".", "/"}]
    if parts:
        stem = parts[0].replace(".py", "").replace(".sql", "")
        return {"owner": stem, "team": "unassigned"}
    return {"owner": "unknown", "team": "unassigned"}


def parse_taxonomy_annotations(blob: str) -> dict[str, Any]:
    """Parse taxonomy: key=value annotations and tables: shorthand from text."""
    result: dict[str, Any] = {}
    tables: list[str] = []

    for m in TAXONOMY_META_RE.finditer(blob):
        for km in TAXONOMY_KV_RE.finditer(m.group(0)):
            key = km.group(1).lower()
            val = km.group(2).strip().strip("\"'")
            if key in {"tables", "table"}:
                tables.extend(_split_tables(val))
            elif key == "status" and val.lower() in VALID_STATUSES:
                result["status"] = val.lower()
            elif key == "owner":
                result["owner"] = val
            elif key == "team":
                result["team"] = val

    for m in TABLES_SHORTHAND_RE.finditer(blob):
        tables.extend(_split_tables(m.group("tables")))

    if tables:
        # normalize fqn-ish
        normed = []
        seen: set[str] = set()
        for t in tables:
            t = t.strip().lower().strip('"')
            if not t or t in seen:
                continue
            seen.add(t)
            normed.append(t)
        result["tables"] = normed
    return result


def _split_tables(raw: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,]+", raw) if p.strip()]


def detect_status_from_text(blob: str, default: str = "active") -> str:
    ann = parse_taxonomy_annotations(blob)
    if "status" in ann:
        return ann["status"]
    if DEPRECATED_MARKER_RE.search(blob):
        return "deprecated"
    if EXPERIMENTAL_MARKER_RE.search(blob):
        return "experimental"
    return default


def detect_status_from_openapi_op(op: dict) -> str:
    if not isinstance(op, dict):
        return "active"
    if op.get("deprecated") is True:
        return "deprecated"
    # extension
    for key in ("x-status", "x-lifecycle"):
        val = op.get(key)
        if isinstance(val, str) and val.lower() in VALID_STATUSES:
            return val.lower()
    # description markers
    desc = f"{op.get('summary', '')} {op.get('description', '')}"
    return detect_status_from_text(desc, default="active")


def extract_tables_from_openapi_op(op: dict) -> list[str]:
    if not isinstance(op, dict):
        return []
    tables: list[str] = []
    for key in ("x-tables", "x-table", "x-db-tables", "x-db-table"):
        val = op.get(key)
        if isinstance(val, str):
            tables.extend(_split_tables(val))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    tables.append(item.strip())
    # also scan description for taxonomy annotations
    desc = f"{op.get('summary', '')}\n{op.get('description', '')}"
    ann = parse_taxonomy_annotations(desc)
    tables.extend(ann.get("tables") or [])
    # normalize
    out: list[str] = []
    seen: set[str] = set()
    for t in tables:
        t = t.lower().strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def context_window(content: str, match_start: int, before: int = 400, after: int = 200) -> str:
    """Text near a decorator/CREATE TABLE for annotation parsing."""
    start = max(0, match_start - before)
    end = min(len(content), match_start + after)
    return content[start:end]


def merge_owner(
    existing: dict[str, str] | None,
    new: dict[str, str],
    prefer_existing: bool = True,
) -> dict[str, str]:
    if not existing:
        return dict(new)
    if prefer_existing and existing.get("owner") not in {None, "unknown", ""}:
        out = dict(existing)
        if not out.get("team") and new.get("team"):
            out["team"] = new["team"]
        return out
    return dict(new)


def resolve_table_refs(
    refs: Sequence[str], known_fqns: set[str]
) -> list[str]:
    """Map bare table names to known fqns when unambiguous."""
    by_name: dict[str, list[str]] = {}
    for fqn in known_fqns:
        name = fqn.split(".")[-1]
        by_name.setdefault(name, []).append(fqn)

    resolved: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        ref = ref.lower().strip()
        if not ref:
            continue
        if ref in known_fqns or "." in ref and ref in known_fqns:
            cand = ref
        elif ref in by_name and len(by_name[ref]) == 1:
            cand = by_name[ref][0]
        elif ref in by_name:
            # ambiguous — keep bare name as soft ref
            cand = ref
        else:
            cand = ref
        if cand not in seen:
            seen.add(cand)
            resolved.append(cand)
    return resolved
