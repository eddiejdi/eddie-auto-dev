#!/usr/bin/env python3
"""
Taxonomy cross-domain graph builder.

Liga os três catálogos (variables, tables, apis) por:
  1. Hubs de domínio (entity → domain)
  2. Schema / prefixo de serviço
  3. Heurísticas de nome (path contém nome de tabela)
  4. Co-localização de arquivos (mesmo diretório de origem)

Saídas:
  .taxonomy-catalog/graph.json
  .taxonomy-catalog/GRAPH_REPORT.md
  .taxonomy-catalog/links.csv
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]

SERVICE_DOMAIN: list[tuple[str, str]] = [
    ("btc_trading", "trading"),
    ("clear_trading", "trading"),
    ("mt5_bridge", "trading"),
    ("marketing", "marketing"),
    ("secrets_agent", "secrets"),
    ("nextcloud", "storage"),
    ("tape", "storage"),
    ("storage_portal", "portal"),
    ("wiki", "wiki"),
    ("cmdb", "cmdb"),
    ("banking", "banking"),
    ("belvo", "banking"),
    ("x_agent", "social"),
    ("agent_communication", "ipc"),
    ("operation_agent", "agents"),
    ("meeting_translator", "meetings"),
    ("conube", "ops"),
    ("huggingface", "llm"),
    ("grafana", "monitoring"),
    ("code_runner", "platform"),
    ("ssh_agent", "infra"),
    ("bn_acervo", "acervo"),
    ("user_management", "identity"),
    ("home", "home"),
]

SCHEMA_DOMAIN = {
    "btc": "trading",
    "clear": "trading",
    "marketing": "marketing",
}

VAR_DOMAIN_PATTERNS: list[tuple[str, str]] = [
    (r"(TRADING|EXCHANGE|MT5|BTC|CRYPTO|ORDER|POSITION)", "trading"),
    (r"(TELEGRAM|SLACK|WHATSAPP|X_|TWITTER)", "social"),
    (r"(SECRET|VAULT|BITWARDEN|AUTHENTIK|JWT|TOKEN|PASSWORD)", "secrets"),
    (r"(NEXTCLOUD|LTFS|TAPE|STORAGE|S3|MINIO)", "storage"),
    (r"(WIKI|KNOWLEDGE)", "wiki"),
    (r"(CMDB|GLPI|INVENTORY)", "cmdb"),
    (r"(BANK|BELVO|PAYMENT|BILLING|MERCADOPAGO)", "banking"),
    (r"(MARKETING|LEAD|CAMPAIGN)", "marketing"),
    (r"(OLLAMA|GPU|MODEL|RAG|HF_|HUGGING)", "llm"),
    (r"(GRAFANA|PROMETHEUS|ALERT|MONITOR)", "monitoring"),
    (r"(POSTGRES|DATABASE|DB_|REDIS|MONGO)", "database"),
    (r"(AGENT|COORDINATOR|DIRETOR|IPC|BUS)", "agents"),
]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return {}


def _flatten_catalog(catalog: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for category, entries in (catalog.get("categories") or {}).items():
        if not isinstance(entries, dict):
            continue
        for key, data in entries.items():
            item = dict(data) if isinstance(data, dict) else {"name": key}
            item.setdefault("category", category)
            item["_key"] = key
            out[key] = item
    return out


def _domain_from_service(service: str) -> str | None:
    s = (service or "").lower()
    for hint, domain in SERVICE_DOMAIN:
        if hint in s:
            return domain
    return None


def _domain_from_var(name: str) -> str | None:
    for pattern, domain in VAR_DOMAIN_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return domain
    return None


def _path_tokens(path: str) -> set[str]:
    parts = re.split(r"[/_\-{}]+", path.lower())
    return {p for p in parts if len(p) >= 3}


# Top-level dirs too broad for co-location (would link unrelated modules).
_BROAD_TOP = {
    "specialized_agents",
    "tools",
    "scripts",
    "docs",
    "site",
    "deploy",
    "grafana",
}


def _file_prefix(locations: list) -> set[str]:
    prefixes: set[str] = set()
    for loc in locations or []:
        f = (loc.get("file") or "").replace("\\", "/")
        if not f:
            continue
        parts = f.split("/")
        if len(parts) >= 2:
            # Prefer package/module level: a/b
            prefixes.add(f"{parts[0]}/{parts[1]}")
            # Root package only if not a broad monorepo folder
            if parts[0] not in _BROAD_TOP:
                prefixes.add(parts[0])
        else:
            prefixes.add(parts[0].rsplit(".", 1)[0])
    return prefixes


def _resolve_var_domain(key: str, category: str) -> str:
    if category == "authentication":
        return "secrets"
    if category in {"trading", "database", "monitoring", "infrastructure"}:
        # infrastructure → infra
        return "infra" if category == "infrastructure" else category
    refined = _domain_from_var(key)
    if category in {"services", "integrations", "general"} and refined:
        return refined
    if refined and category in {"services", "integrations"}:
        return refined
    return refined or category or "general"


def build_graph(root: Path = ROOT) -> dict:
    vars_cat = _load_json(root / ".variables-catalog" / "catalog.json")
    tables_cat = _load_json(root / ".tables-catalog" / "catalog.json")
    apis_cat = _load_json(root / ".apis-catalog" / "catalog.json")

    variables = _flatten_catalog(vars_cat)
    tables = _flatten_catalog(tables_cat)
    apis = _flatten_catalog(apis_cat)

    by_domain: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {"variables": [], "tables": [], "apis": []}
    )

    for key, item in variables.items():
        domain = _resolve_var_domain(key, item.get("category") or "")
        item["_domain"] = domain
        by_domain[domain]["variables"].append(key)

    for key, item in tables.items():
        domain = item.get("category") or "general"
        schema = item.get("schema")
        if domain == "general" and schema in SCHEMA_DOMAIN:
            domain = SCHEMA_DOMAIN[schema]
        item["_domain"] = domain
        by_domain[domain]["tables"].append(key)

    for key, item in apis.items():
        domain = item.get("category") or "general"
        if domain == "general":
            domain = _domain_from_service(item.get("service", "")) or "general"
        item["_domain"] = domain
        by_domain[domain]["apis"].append(key)

    edges: list[dict] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    def add_edge(
        src_type: str,
        src: str,
        dst_type: str,
        dst: str,
        relation: str,
        weight: float = 1.0,
        evidence: str = "",
    ) -> None:
        k = (src_type, src, dst_type, dst, relation)
        if k in seen:
            return
        # Prefer stronger relation if pair already linked weakly
        pair = (src_type, src, dst_type, dst)
        existing_idx = None
        for i, e in enumerate(edges):
            if (
                e["from"]["type"] == src_type
                and e["from"]["id"] == src
                and e["to"]["type"] == dst_type
                and e["to"]["id"] == dst
            ):
                existing_idx = i
                break
        if existing_idx is not None:
            if edges[existing_idx]["weight"] >= weight:
                return
            edges[existing_idx] = {
                "from": {"type": src_type, "id": src},
                "to": {"type": dst_type, "id": dst},
                "relation": relation,
                "weight": weight,
                "evidence": evidence,
            }
            return
        seen.add(k)
        edges.append(
            {
                "from": {"type": src_type, "id": src},
                "to": {"type": dst_type, "id": dst},
                "relation": relation,
                "weight": weight,
                "evidence": evidence,
            }
        )

    # 1) Entity → domain hub (compact membership edges)
    # Hub id is the bare domain name; type="domain" → display key domain:trading
    for domain, buckets in by_domain.items():
        hub = domain
        for t in buckets["tables"]:
            add_edge("table", t, "domain", hub, "in_domain", 0.5, f"domain={domain}")
        for a in buckets["apis"]:
            add_edge("api", a, "domain", hub, "in_domain", 0.5, f"domain={domain}")
        # cap variable membership to avoid noise in services dump
        var_list = buckets["variables"]
        if domain in {"services", "general"}:
            var_list = var_list[:50]
        else:
            var_list = var_list[:100]
        for v in var_list:
            add_edge(
                "variable", v, "domain", hub, "in_domain", 0.4, f"domain={domain}"
            )

    # 1b) Explicit API ↔ table links (annotations / OpenAPI x-tables)
    known_fqns = set(tables.keys())
    by_name: dict[str, list[str]] = defaultdict(list)
    for fqn in known_fqns:
        by_name[fqn.split(".")[-1]].append(fqn)

    def _resolve_ref(ref: str) -> list[str]:
        ref = (ref or "").lower().strip()
        if not ref:
            return []
        if ref in known_fqns:
            return [ref]
        if ref in by_name:
            return list(by_name[ref])
        # schema.table not yet in catalog — keep soft ref as-is for evidence
        if "." in ref:
            return [ref]
        return []

    for op_key, api in apis.items():
        for ref in api.get("relatedTables") or []:
            for fqn in _resolve_ref(ref):
                add_edge(
                    "api",
                    op_key,
                    "table",
                    fqn,
                    "explicit",
                    1.0,
                    f"annotation={ref}",
                )
                # reverse on table side if present
                if fqn in tables:
                    rel_apis = set(tables[fqn].get("relatedApis") or [])
                    rel_apis.add(op_key)
                    tables[fqn]["relatedApis"] = sorted(rel_apis)

    for fqn, table in tables.items():
        for op_key in table.get("relatedApis") or []:
            if op_key in apis:
                add_edge(
                    "table",
                    fqn,
                    "api",
                    op_key,
                    "explicit",
                    1.0,
                    "table.relatedApis",
                )

    # 2) Name heuristics: API path tokens ↔ table names
    table_by_name: dict[str, list[str]] = defaultdict(list)
    for fqn, item in tables.items():
        name = item.get("name") or fqn.split(".")[-1]
        table_by_name[name].append(fqn)

    for op_key, api in apis.items():
        tokens = _path_tokens(api.get("path", ""))
        for tok in tokens:
            matches = list(table_by_name.get(tok, []))
            if tok.endswith("s"):
                matches.extend(table_by_name.get(tok[:-1], []))
            for fqn in matches:
                add_edge(
                    "api",
                    op_key,
                    "table",
                    fqn,
                    "name_match",
                    0.9,
                    f"token={tok}",
                )

    # 3) Schema hints: only connection/config-ish vars → tables of that schema
    #    (avoid linking every BTC_* flag to every btc.* table)
    schema_token_map = {
        r"\bBTC_": "btc",
        r"\bCLEAR_": "clear",
        r"\bMARKETING_": "marketing",
    }
    configish = re.compile(
        r"(DATABASE|DB_|POSTGRES|HOST|PORT|URL|SCHEMA|DSN|CONN|USER|PASSWORD|POOL)",
        re.IGNORECASE,
    )
    for var_name in variables:
        if not configish.search(var_name):
            # still allow explicit schema-prefixed config vars like BTC_DB_*
            if not re.search(r"(BTC|CLEAR|MARKETING).*(DB|DATABASE|POSTGRES|SCHEMA)", var_name, re.IGNORECASE):
                continue
        for pattern, schema in schema_token_map.items():
            if re.search(pattern, var_name, re.IGNORECASE):
                for fqn, t in tables.items():
                    if t.get("schema") == schema:
                        add_edge(
                            "variable",
                            var_name,
                            "table",
                            fqn,
                            "schema_hint",
                            0.65,
                            f"var_token={schema}",
                        )

    # DATABASE_URL-like vars → all tables (weak, capped via domain hub only)
    db_vars = [
        v
        for v in variables
        if re.search(r"(DATABASE_URL|POSTGRES_|DB_HOST|DB_NAME)", v, re.IGNORECASE)
    ]
    for v in db_vars[:20]:
        add_edge(
            "variable",
            v,
            "domain",
            "database",
            "in_domain",
            0.7,
            "db_connection_var",
        )

    # 4) File co-location table ↔ api
    table_prefixes = {
        fqn: _file_prefix(item.get("locations")) for fqn, item in tables.items()
    }
    api_prefixes = {
        k: _file_prefix(item.get("locations")) for k, item in apis.items()
    }
    for fqn, tprefs in table_prefixes.items():
        if not tprefs:
            continue
        for op_key, aprefs in api_prefixes.items():
            shared = tprefs & aprefs
            if shared:
                add_edge(
                    "table",
                    fqn,
                    "api",
                    op_key,
                    "colocated",
                    0.85,
                    f"paths={','.join(sorted(shared)[:3])}",
                )

    # 5) Service affinity: apis and tables that share service domain keyword
    #    stronger than in_domain when both map to same SERVICE_DOMAIN hint via files
    for fqn, t in tables.items():
        t_dom = t.get("_domain")
        if not t_dom or t_dom in {"general", "services"}:
            continue
        for op_key, a in apis.items():
            if a.get("_domain") == t_dom:
                # only if not already name_match/colocated — add as soft link
                add_edge(
                    "table",
                    fqn,
                    "api",
                    op_key,
                    "domain_affinity",
                    0.55,
                    f"domain={t_dom}",
                )

    # Cap domain_affinity edges: keep max 8 apis per table (highest weight already preferred)
    affinity = [
        e for e in edges if e["relation"] == "domain_affinity" and e["from"]["type"] == "table"
    ]
    by_table: dict[str, list[dict]] = defaultdict(list)
    for e in affinity:
        by_table[e["from"]["id"]].append(e)
    drop: set[int] = set()
    edge_id = {id(e): i for i, e in enumerate(edges)}
    for fqn, elist in by_table.items():
        if len(elist) <= 8:
            continue
        # keep first 8 (stable)
        for e in elist[8:]:
            drop.add(edge_id[id(e)])
    if drop:
        edges = [e for i, e in enumerate(edges) if i not in drop]

    nodes = {
        "variables": len(variables),
        "tables": len(tables),
        "apis": len(apis),
        "domains": len(by_domain),
    }

    domain_summary = {
        d: {k: len(v) for k, v in buckets.items()}
        for d, buckets in sorted(by_domain.items())
    }

    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[f"{e['from']['type']}:{e['from']['id']}"] += 1
        degree[f"{e['to']['type']}:{e['to']['id']}"] += 1
    top_linked = sorted(degree.items(), key=lambda x: -x[1])[:30]

    # Strong entity-entity edges only (exclude pure domain membership for sample)
    strong = [
        e
        for e in edges
        if e.get("weight", 0) >= 0.8 and e["relation"] != "in_domain"
    ]

    return {
        "catalogVersion": "1.0.0",
        "generatedAt": datetime.now().isoformat(),
        "nodes": nodes,
        "edgeCount": len(edges),
        "domains": domain_summary,
        "topLinked": [{"id": k, "degree": v} for k, v in top_linked],
        "strongEdgeCount": len(strong),
        "edges": edges,
        "relationTypes": sorted({e["relation"] for e in edges}),
    }


def write_reports(graph: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    graph_path = out_dir / "graph.json"
    graph_path.write_text(json.dumps(graph, indent=2, default=str))
    logger.info(f"💾 Graph: {graph_path} ({graph['edgeCount']} edges)")

    csv_lines = ["from_type,from_id,to_type,to_id,relation,weight,evidence"]
    for e in graph["edges"]:
        csv_lines.append(
            f"{e['from']['type']},{e['from']['id']},{e['to']['type']},"
            f"{e['to']['id']},{e['relation']},{e['weight']},"
            f"\"{e.get('evidence', '')}\""
        )
    (out_dir / "links.csv").write_text("\n".join(csv_lines))

    lines = [
        "# Taxonomy Cross-Domain Graph\n\n",
        f"**Generated:** {graph['generatedAt']}\n\n",
        f"**Nodes:** variables={graph['nodes']['variables']}, "
        f"tables={graph['nodes']['tables']}, apis={graph['nodes']['apis']}, "
        f"domains={graph['nodes'].get('domains', 0)}\n\n",
        f"**Edges:** {graph['edgeCount']} "
        f"(strong entity links ≈ {graph.get('strongEdgeCount', 0)})\n\n",
        f"**Relation types:** {', '.join(graph.get('relationTypes') or [])}\n\n",
        "---\n\n",
        "## Domains\n\n",
        "| Domain | Variables | Tables | APIs |\n",
        "|--------|----------:|-------:|-----:|\n",
    ]
    for domain, counts in graph.get("domains", {}).items():
        lines.append(
            f"| {domain} | {counts.get('variables', 0)} | "
            f"{counts.get('tables', 0)} | {counts.get('apis', 0)} |\n"
        )
    lines.append("\n## Top linked entities\n\n")
    for item in graph.get("topLinked", [])[:20]:
        lines.append(f"- `{item['id']}` (degree={item['degree']})\n")

    strong = [
        e
        for e in graph["edges"]
        if e.get("weight", 0) >= 0.8 and e["relation"] != "in_domain"
    ][:50]
    lines.append("\n## High-confidence entity links (sample)\n\n")
    if not strong:
        lines.append("_Nenhum link de alta confiança além de membership de domínio._\n")
    for e in strong:
        lines.append(
            f"- `{e['from']['type']}:{e['from']['id']}` "
            f"—[{e['relation']}]→ "
            f"`{e['to']['type']}:{e['to']['id']}` "
            f"({e.get('evidence', '')})\n"
        )
    (out_dir / "GRAPH_REPORT.md").write_text("".join(lines))
    logger.info(f"✅ Graph report: {out_dir / 'GRAPH_REPORT.md'}")


def main() -> int:
    graph = build_graph(ROOT)
    write_reports(graph, ROOT / ".taxonomy-catalog")
    logger.info(
        f"Graph complete: {graph['edgeCount']} edges across "
        f"{graph['nodes'].get('domains', 0)} domains"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
