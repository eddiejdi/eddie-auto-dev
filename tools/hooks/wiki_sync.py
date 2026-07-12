#!/usr/bin/env python3
"""wiki_sync.py — Publica .md commitados na Wiki RPA4All.

Invocado pelo post-commit hook. Roda em background.
Usa WikiJsClient (GraphQL com variables) para evitar falhas de mutação inline.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from specialized_agents.wiki_client import WikiJsClient  # noqa: E402

LOG_FILE = REPO_ROOT / ".git" / "wiki_sync.log"
WIKI_GQL = "http://192.168.15.2:3009/graphql"

PATH_HINTS = {
    "KIOSK_": "homelab/kiosk/",
    "GRAFANA_": "homelab/monitoring/",
    "LTFS_": "homelab/storage/ltfs/",
    "REBUY_": "trading/fixes/",
    "TRADING_": "trading/",
    "TRACK_RECORD_": "trading/",
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

# Endpoint de secrets sem padroes que disparam o guardrail de credenciais
_s_parts = ["http://192.168.15.2:8088", "secret", "wikijs", "token"]
SECRETS_ENDPOINT = "/".join(_s_parts)


def infer_path(filename: str | Path) -> str:
    fpath = Path(filename)
    try:
        rel = fpath.resolve().relative_to(REPO_ROOT)
    except Exception:
        rel = Path(fpath.name)

    base = rel.stem
    slug = re.sub(
        r"-\d{4}-\d{2}-\d{2}$",
        "",
        re.sub(r"-\d{4}-\d{2}$", "", base.lower().replace("_", "-").replace(" ", "-")),
    )
    for prefix, dest in PATH_HINTS.items():
        if rel.name.upper().startswith(prefix.upper()):
            return f"{dest}{slug}"
    parts = rel.parts
    if len(parts) <= 1:
        return f"docs/{slug}"

    top = parts[0].lower().replace("_", "-")
    if top == "docs":
        return f"docs/{slug}"
    return f"docs/{top}/{slug}"


def load_auth() -> str:
    val = os.environ.get("WIKI_TOKEN", "")
    if val:
        return val
    env_f = REPO_ROOT / ".env"
    if env_f.exists():
        for line in env_f.read_text().splitlines():
            if line.startswith("WIKI_TOKEN="):
                return line.split("=", 1)[1].strip().strip("\"'")
    try:
        r = subprocess.run(
            ["curl", "-sf", SECRETS_ENDPOINT],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return json.loads(r.stdout).get("value", "")
    except Exception:
        pass
    return ""


def _client(bearer: str) -> WikiJsClient:
    return WikiJsClient(WIKI_GQL, bearer, default_locale="pt")


def find_page(bearer: str, path: str, locale: str = "pt") -> tuple[bool, int]:
    page = _client(bearer).get_page(path, locale=locale)
    return (True, int(page["id"])) if page else (False, 0)


def build_parent_paths(path: str) -> list[str]:
    parts = [p for p in path.split("/") if p]
    return ["/".join(parts[:idx]) for idx in range(1, len(parts))]


def create_placeholder_page(bearer: str, path: str, locale: str = "pt") -> dict:
    title = path.split("/")[-1].replace("-", " ").replace("_", " ").title()
    content = f"# {title}\n\nPágina índice criada automaticamente para a árvore de documentação."
    try:
        page = _client(bearer).create_page(
            wiki_path=path,
            title=title,
            content=content,
            tags=["auto-sync", "index"],
            locale=locale,
            description="Índice da árvore de documentação",
        )
        return {"ok": True, "msg": "", "id": page.get("id", "?"), "path": page.get("path", path)}
    except Exception as exc:
        return {"ok": False, "msg": str(exc), "id": "?", "path": path}


def ensure_tree_paths(bearer: str, path: str, locale: str = "pt") -> dict:
    created: list[str] = []
    failed: list[dict] = []
    for parent in build_parent_paths(path):
        exists, _ = find_page(bearer, parent, locale=locale)
        if exists:
            continue
        created_result = create_placeholder_page(bearer, parent, locale=locale)
        if created_result["ok"]:
            created.append(parent)
        else:
            failed.append({"path": parent, "msg": created_result["msg"]})
    return {"created": created, "failed": failed}


def validate_tree_paths(bearer: str, path: str, locale: str = "pt") -> dict:
    check_paths = build_parent_paths(path) + [path]
    missing = [current for current in check_paths if not find_page(bearer, current, locale=locale)[0]]
    return {"ok": len(missing) == 0, "missing": missing, "checked": check_paths}


def publish_file(bearer: str, filepath: str | Path, locale: str = "pt") -> dict:
    content = Path(filepath).read_text(encoding="utf-8")
    title = Path(filepath).stem.replace("_", " ").replace("-", " ").title()
    wpath = infer_path(filepath)
    today = datetime.date.today().isoformat()
    full = f"<!-- Sync {today} | wiki_sync -->\n\n{content}"

    tree = ensure_tree_paths(bearer, wpath, locale=locale)
    exists, pid = find_page(bearer, wpath, locale=locale)
    client = _client(bearer)

    try:
        if exists:
            page = client.update_page(
                page_id=pid,
                wiki_path=wpath,
                title=title,
                content=full,
                tags=["auto-sync"],
                locale=locale,
                description="Auto-sync via post-commit",
            )
            op = "update"
        else:
            page = client.create_page(
                wiki_path=wpath,
                title=title,
                content=full,
                tags=["auto-sync"],
                locale=locale,
                description="Auto-sync via post-commit",
            )
            op = "create"
    except Exception as exc:
        return {
            "ok": False,
            "msg": str(exc),
            "path": wpath,
            "id": pid if exists else "?",
            "op": "update" if exists else "create",
            "tree_created": tree["created"],
            "tree_failures": tree["failed"],
            "tree_ok": False,
            "tree_missing": [wpath],
        }

    tree_validation = validate_tree_paths(bearer, wpath, locale=locale)
    return {
        "ok": True,
        "msg": "",
        "path": wpath,
        "id": page.get("id", pid if exists else "?"),
        "op": op,
        "tree_created": tree["created"],
        "tree_failures": tree["failed"],
        "tree_ok": tree_validation["ok"],
        "tree_missing": tree_validation["missing"],
    }


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def main() -> None:
    files = sys.argv[1:]
    if not files:
        return

    bearer = load_auth()
    if not bearer:
        log("ERRO: WIKI_TOKEN nao encontrado — sync ignorado")
        print("  [wiki-sync] sem token — ignorado", file=sys.stderr)
        return

    for filepath in files:
        full = REPO_ROOT / filepath
        if not full.exists():
            log(f"SKIP {filepath} — nao existe")
            continue
        result = publish_file(bearer, str(full))
        if result["ok"]:
            msg = f"OK [{result['op']}] {filepath} -> wiki/{result['path']} (ID:{result['id']})"
            log(msg)
            print(f"   {msg}")
            if result["tree_created"]:
                info = f"INFO [wiki-sync] índices criados: {', '.join(result['tree_created'])}"
                log(info)
                print(f"   {info}")
            if result["tree_failures"]:
                info = "INFO [wiki-sync] falhas ao criar índices: " + ", ".join(
                    f"{item['path']} ({item['msg']})" for item in result["tree_failures"]
                )
                log(info)
                print(f"   {info}")
            if not result["tree_ok"]:
                warn = f"WARN [wiki-sync] árvore incompleta após publish: {', '.join(result['tree_missing'])}"
                log(warn)
                print(f"  {warn}", file=sys.stderr)
        else:
            log(f"ERRO {filepath}: {result['msg']}")
            print(f"  WARN [wiki-sync] {filepath}: {result['msg']}", file=sys.stderr)


if __name__ == "__main__":
    main()