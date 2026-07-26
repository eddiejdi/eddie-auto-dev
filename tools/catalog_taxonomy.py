#!/usr/bin/env python3
"""
Taxonomy Catalog Orchestrator

Gera (ou atualiza) os três domínios da taxonomia do homelab:
  - variables  → tools/catalog_variables.py  → .variables-catalog/
  - tables     → tools/catalog_tables.py     → .tables-catalog/
  - apis       → tools/catalog_apis.py       → .apis-catalog/

Uso:
  python3 tools/catalog_taxonomy.py              # todos os domínios
  python3 tools/catalog_taxonomy.py --domain tables
  python3 tools/catalog_taxonomy.py --domain apis,variables
  python3 tools/catalog_taxonomy.py --reports-only
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOMAINS = ("variables", "tables", "apis")


def _parse_domains(raw: str) -> List[str]:
    if not raw or raw.strip().lower() in {"all", "*"}:
        return list(DOMAINS)
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    unknown = [p for p in parts if p not in DOMAINS]
    if unknown:
        raise SystemExit(f"Domínios desconhecidos: {unknown}. Válidos: {DOMAINS}")
    return parts


def run_variables(reports: bool = True) -> dict:
    from tools.catalog_variables import VariablesCatalog

    cat = VariablesCatalog(root_path=str(ROOT))
    data = cat.generate_catalog()
    cat.save_catalog()
    if reports:
        try:
            from tools.catalog_reporter import CatalogReporter

            reporter = CatalogReporter(str(ROOT / ".variables-catalog" / "catalog.json"))
            reporter.generate_markdown_report()
            reporter.generate_csv_report()
            reporter.generate_service_report()
        except Exception as e:
            logger.warning(f"Variables reports failed: {e}")
    return {
        "domain": "variables",
        "total": data.get("metadata", {}).get("totalVariables", 0),
        "output": str(ROOT / ".variables-catalog" / "catalog.json"),
    }


def run_tables(reports: bool = True) -> dict:
    from tools.catalog_tables import TablesCatalog

    cat = TablesCatalog(root_path=str(ROOT))
    data = cat.generate_catalog()
    cat.save_catalog()
    if reports:
        cat.generate_reports()
    return {
        "domain": "tables",
        "total": data.get("metadata", {}).get("totalTables", 0),
        "output": str(ROOT / ".tables-catalog" / "catalog.json"),
    }


def run_apis(reports: bool = True) -> dict:
    from tools.catalog_apis import ApisCatalog

    cat = ApisCatalog(root_path=str(ROOT))
    data = cat.generate_catalog()
    cat.save_catalog()
    if reports:
        cat.generate_reports()
    return {
        "domain": "apis",
        "total": data.get("metadata", {}).get("totalEndpoints", 0),
        "output": str(ROOT / ".apis-catalog" / "catalog.json"),
    }


RUNNERS = {
    "variables": run_variables,
    "tables": run_tables,
    "apis": run_apis,
}


def write_index(results: Iterable[dict], graph_meta: dict | None = None) -> Path:
    """Escreve índice unificado da taxonomia expandida."""
    index_dir = ROOT / ".taxonomy-catalog"
    index_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "catalogVersion": "1.1.0",
        "generatedAt": datetime.now().isoformat(),
        "domains": list(results),
        "graph": graph_meta or {},
        "docs": {
            "quickStart": "TAXONOMY_QUICK_START.md",
            "overview": "docs/taxonomy/README.md",
            "architecture": "docs/taxonomy/ARCHITECTURE.md",
            "operations": "docs/taxonomy/OPERATIONS.md",
            "annotations": "docs/taxonomy/ANNOTATIONS.md",
            "enforcement": "docs/taxonomy/ENFORCEMENT.md",
            "variables": "docs/variables-taxonomy/README.md",
            "tables": "docs/taxonomy/TABLES.md",
            "apis": "docs/taxonomy/APIS.md",
            "graph": "docs/taxonomy/GRAPH.md",
            "ownership": "docs/taxonomy/OWNERSHIP.md",
            "domainMap": "docs/taxonomy/DOMAIN_MAP.md",
        },
        "artifacts": {
            "variables": ".variables-catalog/catalog.json",
            "tables": ".tables-catalog/catalog.json",
            "apis": ".apis-catalog/catalog.json",
            "graph": ".taxonomy-catalog/graph.json",
            "graphReport": ".taxonomy-catalog/GRAPH_REPORT.md",
            "links": ".taxonomy-catalog/links.csv",
            "orphans": ".taxonomy-catalog/ORPHANS.md",
            "ownershipGaps": ".taxonomy-catalog/OWNERSHIP_GAPS.md",
            "domainMap": ".taxonomy-catalog/DOMAIN_MAP.md",
            "lifecycle": ".taxonomy-catalog/lifecycle_summary.json",
        },
    }
    out = index_dir / "index.json"
    out.write_text(json.dumps(payload, indent=2))
    logger.info(f"💾 Taxonomy index: {out}")
    return out


def run_graph() -> dict:
    from tools.catalog_taxonomy_graph import build_graph, write_reports

    logger.info("\n>>> Building cross-domain graph")
    graph = build_graph(ROOT)
    write_reports(graph, ROOT / ".taxonomy-catalog")
    return {
        "edgeCount": graph.get("edgeCount", 0),
        "strongEdgeCount": graph.get("strongEdgeCount", 0),
        "domains": len(graph.get("domains") or {}),
        "output": str(ROOT / ".taxonomy-catalog" / "graph.json"),
    }


def run_lifecycle() -> dict:
    from tools.catalog_taxonomy_lifecycle import run_lifecycle as _run

    logger.info("\n>>> Lifecycle inference (unused / orphans / ownership gaps)")
    return _run(ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Homelab taxonomy orchestrator")
    parser.add_argument(
        "--domain",
        default="all",
        help="Domínios: all | variables | tables | apis | csv (ex: tables,apis)",
    )
    parser.add_argument(
        "--no-reports",
        action="store_true",
        help="Só gera catalog.json, sem reports MD/CSV",
    )
    parser.add_argument(
        "--no-graph",
        action="store_true",
        help="Não gera o grafo cruzado tables↔apis↔variables",
    )
    parser.add_argument(
        "--graph-only",
        action="store_true",
        help="Só reconstrói o grafo a partir dos catálogos existentes",
    )
    parser.add_argument(
        "--no-lifecycle",
        action="store_true",
        help="Não infere unused/orphans após o grafo",
    )
    parser.add_argument(
        "--lifecycle-only",
        action="store_true",
        help="Só roda lifecycle sobre catálogos/grafo existentes",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("🏷  TAXONOMY CATALOG ORCHESTRATOR")
    logger.info("=" * 70)

    results = []
    if args.lifecycle_only:
        life = run_lifecycle()
        write_index(results, {"lifecycle": life})
        logger.info(f"✅ Lifecycle only: {life}")
        return 0 if not life.get("error") else 1

    if args.graph_only:
        graph_meta = run_graph()
        life = {} if args.no_lifecycle else run_lifecycle()
        graph_meta = {**graph_meta, "lifecycle": life}
        write_index(results, graph_meta)
        logger.info(f"✅ Graph only: {graph_meta}")
        return 0

    domains = _parse_domains(args.domain)
    reports = not args.no_reports
    logger.info(f"   Domains: {', '.join(domains)}")

    for domain in domains:
        logger.info(f"\n>>> Running domain: {domain}")
        results.append(RUNNERS[domain](reports=reports))

    graph_meta = {}
    if not args.no_graph:
        graph_meta = run_graph()
        if not args.no_lifecycle:
            graph_meta["lifecycle"] = run_lifecycle()

    write_index(results, graph_meta)

    logger.info("\n" + "=" * 70)
    logger.info("✅ Taxonomy update complete")
    for r in results:
        logger.info(f"  • {r['domain']}: {r['total']} items → {r['output']}")
    if graph_meta:
        logger.info(
            f"  • graph: {graph_meta.get('edgeCount', 0)} edges "
            f"(strong={graph_meta.get('strongEdgeCount', 0)}) → {graph_meta.get('output')}"
        )
        life = graph_meta.get("lifecycle") or {}
        if life:
            logger.info(
                f"  • lifecycle: unused_tables={life.get('unusedTables', 0)} "
                f"orphan_apis={life.get('orphanApis', 0)}"
            )
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
