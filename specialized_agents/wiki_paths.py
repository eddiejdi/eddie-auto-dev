from __future__ import annotations

import re
from pathlib import Path


PATH_HINTS = {
    "KIOSK_": "homelab/kiosk/",
    "GRAFANA_": "homelab/monitoring/",
    "LTFS_": "homelab/storage/ltfs/",
    "REBUY_": "trading/fixes/",
    "TRADING_": "trading/",
    "DEPOSIT_": "trading/fixes/",
    "LIQUIDACAO_": "trading/",
    "EXCHANGE_": "trading/",
    "DEPLOYMENT_": "operations/deploy/",
    "MONITORING_": "homelab/monitoring/",
    "PLC_": "homelab/plc/",
    "PXE_": "homelab/network/pxe/",
    "INTERNET_": "homelab/network/",
    "IVENTOY_": "homelab/network/pxe/",
    "RELATORIO_": "operations/reports/",
    "QUICK_REFERENCE": "operations/",
    "README_": "docs/",
}


def normalize_slug(value: str) -> str:
    """Normaliza nomes de arquivo ou segmentos de path para a wiki."""
    slug = value.strip().lower().replace("_", "-").replace(" ", "-")
    slug = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", slug)
    slug = re.sub(r"-\d{4}-\d{2}$", "", slug)
    slug = re.sub(r"[^a-z0-9/-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")


def _normalize_segment(segment: str) -> str:
    return normalize_slug(segment)


def canonical_wiki_path(filename: str, repo_root: Path | None = None) -> str:
    """
    Resolve o caminho canônico de uma página wiki a partir do arquivo local.

    Regras principais:
    - docs/*.md                     -> docs/<slug>
    - docs/INCIDENTS/*.md          -> docs/incidents/<slug>
    - docs/agents/*.md             -> docs/agents/<slug>
    - docs/archive/*.md            -> docs/archive/<slug>
    - docs/**/x.md                 -> docs/<subtree>/<slug>
    - demais arquivos usam PATH_HINTS ou docs/<top>/<slug>
    """
    fpath = Path(filename)
    if repo_root is not None:
        try:
            rel = fpath.resolve().relative_to(repo_root.resolve())
        except Exception:
            rel = fpath
    else:
        rel = fpath

    name = rel.name
    stem_slug = normalize_slug(rel.stem)
    upper_name = name.upper()

    for prefix, dest in PATH_HINTS.items():
        if upper_name.startswith(prefix.upper()):
            return f"{dest}{stem_slug}"

    parts = rel.parts
    if len(parts) <= 1:
        return f"docs/{stem_slug}"

    top = _normalize_segment(parts[0])
    if top != "docs":
        return f"docs/{top}/{stem_slug}"

    # docs/*
    if len(parts) == 2:
        return f"docs/{stem_slug}"

    subtree = [_normalize_segment(p) for p in parts[1:-1] if p]
    return "/".join(["docs", *subtree, stem_slug])
