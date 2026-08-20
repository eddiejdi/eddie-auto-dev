#!/usr/bin/env python3
"""
Lifecycle inference for taxonomy catalogs.

After the cross-domain graph is built:
  - Tables with no strong entity links → status=unused (unless deprecated/experimental)
  - Generate ORPHANS.md + OWNERSHIP_GAPS.md + mermaid domain map

Strong links: explicit | name_match | colocated  (weight >= 0.8)
domain_affinity / in_domain alone do NOT protect against unused.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]

STRONG_RELATIONS = frozenset({"explicit", "name_match", "colocated"})
PROTECTED_STATUSES = frozenset({"deprecated", "experimental"})


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"load failed {path}: {e}")
        return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def _flatten(catalog: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for cat, entries in (catalog.get("categories") or {}).items():
        if not isinstance(entries, dict):
            continue
        for key, data in entries.items():
            item = dict(data) if isinstance(data, dict) else {"name": key}
            item["_category"] = cat
            item["_key"] = key
            out[key] = item
    return out


def entities_with_strong_links(graph: dict) -> tuple[set[str], set[str]]:
    """Return (tables_with_strong, apis_with_strong) using type:id keys stripped."""
    tables: set[str] = set()
    apis: set[str] = set()
    for e in graph.get("edges") or []:
        if e.get("relation") not in STRONG_RELATIONS:
            continue
        if e.get("weight", 0) < 0.8:
            continue
        for side in ("from", "to"):
            node = e.get(side) or {}
            ntype, nid = node.get("type"), node.get("id")
            if ntype == "table":
                tables.add(nid)
            elif ntype == "api":
                apis.add(nid)
    return tables, apis


def apply_unused_to_tables(
    tables_catalog: dict, linked_tables: set[str]
) -> tuple[dict, list[str]]:
    """Mutate catalog: mark unlinked tables as unused. Return (catalog, newly_unused)."""
    newly: list[str] = []
    status_counts: dict[str, int] = defaultdict(int)

    for cat, entries in (tables_catalog.get("categories") or {}).items():
        if not isinstance(entries, dict):
            continue
        for fqn, data in entries.items():
            if not isinstance(data, dict):
                continue
            current = data.get("status") or "active"
            if current in PROTECTED_STATUSES:
                status_counts[current] += 1
                continue
            if fqn in linked_tables:
                # restore unused → active if it gained links
                if current == "unused":
                    data["status"] = "active"
                    data["lifecycleReason"] = "strong_link_present"
                else:
                    data.setdefault("status", "active")
                status_counts[data["status"]] += 1
            else:
                if current != "unused":
                    newly.append(fqn)
                data["status"] = "unused"
                data["lifecycleReason"] = (
                    "no_strong_api_link (missing explicit/name_match/colocated)"
                )
                status_counts["unused"] += 1

    meta = tables_catalog.setdefault("metadata", {})
    meta["statusCounts"] = dict(status_counts)
    meta["unusedCount"] = status_counts.get("unused", 0)
    meta["lifecycleUpdatedAt"] = datetime.now().isoformat()
    return tables_catalog, newly


def annotate_api_orphan_flags(
    apis_catalog: dict, linked_apis: set[str]
) -> tuple[dict, list[str]]:
    """
    APIs are NOT auto-set to unused (too noisy).
    Flag orphan=true when no strong table link and no relatedTables.
    """
    orphans: list[str] = []
    for cat, entries in (apis_catalog.get("categories") or {}).items():
        if not isinstance(entries, dict):
            continue
        for key, data in entries.items():
            if not isinstance(data, dict):
                continue
            has_rel = bool(data.get("relatedTables"))
            has_strong = key in linked_apis
            path = data.get("path") or ""
            is_health = (
                data.get("category") == "health"
                or path in {"/health", "/", "/metrics", "/ready", "/live"}
                or path.endswith("/health")
            )
            is_orphan = (not has_rel and not has_strong and not is_health)
            data["orphan"] = is_orphan
            if is_orphan:
                orphans.append(key)
    meta = apis_catalog.setdefault("metadata", {})
    meta["orphanCount"] = len(orphans)
    meta["lifecycleUpdatedAt"] = datetime.now().isoformat()
    return apis_catalog, orphans


def ownership_gaps(tables: dict, apis: dict) -> dict[str, list[str]]:
    gaps = {
        "tables_unknown_owner": [],
        "tables_unassigned_team": [],
        "apis_unknown_owner": [],
        "apis_unassigned_team": [],
    }
    for fqn, d in tables.items():
        if d.get("owner") in {None, "", "unknown"}:
            gaps["tables_unknown_owner"].append(fqn)
        if d.get("team") in {None, "", "unassigned"}:
            gaps["tables_unassigned_team"].append(fqn)
    for key, d in apis.items():
        if d.get("owner") in {None, "", "unknown"}:
            gaps["apis_unknown_owner"].append(key)
        if d.get("team") in {None, "", "unassigned"}:
            gaps["apis_unassigned_team"].append(key)
    return gaps


def write_orphan_report(
    out_dir: Path,
    unused_tables: list[str],
    orphan_apis: list[str],
    tables_flat: dict[str, dict],
    apis_flat: dict[str, dict],
) -> Path:
    lines = [
        "# Taxonomy Orphans & Unused\n\n",
        f"**Generated:** {datetime.now().isoformat()}\n\n",
        "Tables without strong API links are marked `status=unused`.\n",
        "APIs without table links are flagged `orphan=true` (status unchanged).\n\n",
        "---\n\n",
        f"## Unused tables ({len(unused_tables)})\n\n",
    ]
    if not unused_tables:
        lines.append("_Nenhuma tabela órfã._\n\n")
    for fqn in sorted(unused_tables):
        t = tables_flat.get(fqn, {})
        lines.append(
            f"- `{fqn}` — owner=`{t.get('owner')}` category=`{t.get('_category')}`\n"
        )

    lines.append(f"\n## Orphan APIs (no table link) ({len(orphan_apis)})\n\n")
    # group by category
    by_cat: dict[str, list[str]] = defaultdict(list)
    for key in orphan_apis:
        by_cat[apis_flat.get(key, {}).get("_category", "general")].append(key)
    for cat in sorted(by_cat):
        lines.append(f"### {cat} ({len(by_cat[cat])})\n\n")
        for key in sorted(by_cat[cat])[:40]:
            a = apis_flat.get(key, {})
            lines.append(f"- `{key}` — service=`{a.get('service')}`\n")
        if len(by_cat[cat]) > 40:
            lines.append(f"- … and {len(by_cat[cat]) - 40} more\n")
        lines.append("\n")

    lines.append(
        "\n## How to fix\n\n"
        "1. Add `# taxonomy: tables=schema.table` above the route\n"
        "2. Or OpenAPI `x-tables: [schema.table]`\n"
        "3. Re-run `python3 tools/catalog_taxonomy.py --domain tables,apis`\n"
    )
    path = out_dir / "ORPHANS.md"
    path.write_text("".join(lines))
    logger.info(f"✅ {path}")
    return path


def write_ownership_gaps_report(out_dir: Path, gaps: dict[str, list[str]]) -> Path:
    lines = [
        "# Taxonomy Ownership Gaps\n\n",
        f"**Generated:** {datetime.now().isoformat()}\n\n",
    ]
    for key, items in gaps.items():
        lines.append(f"## {key} ({len(items)})\n\n")
        for item in sorted(items)[:50]:
            lines.append(f"- `{item}`\n")
        if len(items) > 50:
            lines.append(f"- … and {len(items) - 50} more\n")
        lines.append("\n")
    lines.append(
        "Fix: edit `OWNER_RULES` in `tools/taxonomy_meta.py` "
        "or add `taxonomy: owner=...; team=...` annotations.\n"
    )
    path = out_dir / "OWNERSHIP_GAPS.md"
    path.write_text("".join(lines))
    logger.info(f"✅ {path}")
    return path


def write_mermaid_map(out_dir: Path, graph: dict) -> Path:
    """Compact domain-level mermaid diagram for wiki/docs."""
    domains = graph.get("domains") or {}
    lines = [
        "# Taxonomy Domain Map\n\n",
        f"**Generated:** {datetime.now().isoformat()}\n\n",
        "Diagrama Mermaid dos hubs de domínio (contagens do grafo).\n\n",
        "```mermaid\n",
        "flowchart LR\n",
        "  classDef hub fill:#1f2937,stroke:#93c5fd,color:#e5e7eb\n",
    ]
    # only domains with tables or apis
    interesting = {
        d: c
        for d, c in domains.items()
        if (c.get("tables", 0) + c.get("apis", 0)) > 0 and d not in {"services", "general"}
    }
    for domain, counts in sorted(
        interesting.items(),
        key=lambda x: -(x[1].get("tables", 0) + x[1].get("apis", 0)),
    )[:20]:
        safe = domain.replace("-", "_").replace(" ", "_")
        label = (
            f"{domain}\\n"
            f"T:{counts.get('tables', 0)} "
            f"A:{counts.get('apis', 0)} "
            f"V:{counts.get('variables', 0)}"
        )
        lines.append(f"  {safe}[\"{label}\"]:::hub\n")

    # soft links between related domains
    pairs = [
        ("trading", "secrets"),
        ("trading", "database"),
        ("trading", "llm"),
        ("storage", "secrets"),
        ("marketing", "social"),
        ("agents", "llm"),
        ("agents", "ipc"),
        ("banking", "secrets"),
        ("portal", "storage"),
        ("wiki", "llm"),
        ("monitoring", "infra"),
    ]
    for a, b in pairs:
        if a in interesting and b in interesting:
            sa = a.replace("-", "_")
            sb = b.replace("-", "_")
            lines.append(f"  {sa} -.-> {sb}\n")
    lines.append("```\n\n")
    body = "".join(lines)
    path = out_dir / "DOMAIN_MAP.md"
    path.write_text(
        body + "Ver também: [docs/taxonomy/GRAPH.md](../docs/taxonomy/GRAPH.md), "
        "`graph.json`, [TAXONOMY_QUICK_START.md](../TAXONOMY_QUICK_START.md).\n"
    )
    # also copy-friendly under docs (relative links inside docs/taxonomy/)
    docs_path = ROOT / "docs" / "taxonomy" / "DOMAIN_MAP.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(
        body
        + "Ver também: [GRAPH.md](./GRAPH.md), [README.md](./README.md), "
        "[TAXONOMY_QUICK_START.md](../../TAXONOMY_QUICK_START.md).\n"
    )
    logger.info(f"✅ {path} + {docs_path}")
    return path


def run_lifecycle(root: Path = ROOT) -> dict:
    graph_path = root / ".taxonomy-catalog" / "graph.json"
    tables_path = root / ".tables-catalog" / "catalog.json"
    apis_path = root / ".apis-catalog" / "catalog.json"
    out_dir = root / ".taxonomy-catalog"

    graph = _load(graph_path)
    tables_cat = _load(tables_path)
    apis_cat = _load(apis_path)

    if not graph:
        logger.warning("No graph.json — run catalog_taxonomy_graph first")
        return {"error": "no_graph"}

    linked_tables, linked_apis = entities_with_strong_links(graph)
    tables_cat, newly_unused = apply_unused_to_tables(tables_cat, linked_tables)
    apis_cat, orphan_apis = annotate_api_orphan_flags(apis_cat, linked_apis)

    # recompute which are currently unused (full list)
    unused_all = []
    for cat, entries in (tables_cat.get("categories") or {}).items():
        for fqn, data in (entries or {}).items():
            if isinstance(data, dict) and data.get("status") == "unused":
                unused_all.append(fqn)

    _save(tables_path, tables_cat)
    _save(apis_path, apis_cat)

    tables_flat = _flatten(tables_cat)
    apis_flat = _flatten(apis_cat)
    gaps = ownership_gaps(tables_flat, apis_flat)

    write_orphan_report(out_dir, unused_all, orphan_apis, tables_flat, apis_flat)
    write_ownership_gaps_report(out_dir, gaps)
    write_mermaid_map(out_dir, graph)

    # refresh table report status section if reporter exists
    try:
        from tools.catalog_tables import TablesCatalog

        # lightweight re-report from saved catalog
        tc = TablesCatalog(root_path=str(root))
        tc.catalog = tables_cat
        tc.tables = tables_flat
        # categories already set
        tc.generate_reports(output_dir=root / ".tables-catalog")
    except Exception as e:
        logger.warning(f"table report refresh skipped: {e}")

    try:
        from tools.catalog_apis import ApisCatalog

        ac = ApisCatalog(root_path=str(root))
        ac.catalog = apis_cat
        ac.endpoints = apis_flat
        ac.generate_reports(output_dir=root / ".apis-catalog")
    except Exception as e:
        logger.warning(f"api report refresh skipped: {e}")

    summary = {
        "linkedTables": len(linked_tables),
        "linkedApis": len(linked_apis),
        "unusedTables": len(unused_all),
        "newlyUnused": len(newly_unused),
        "orphanApis": len(orphan_apis),
        "ownershipGaps": {k: len(v) for k, v in gaps.items()},
    }
    (out_dir / "lifecycle_summary.json").write_text(json.dumps(summary, indent=2))
    logger.info(f"Lifecycle: {summary}")
    return summary


def main() -> int:
    summary = run_lifecycle(ROOT)
    if summary.get("error"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
