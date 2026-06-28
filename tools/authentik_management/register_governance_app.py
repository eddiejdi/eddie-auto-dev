#!/usr/bin/env python3
"""
Registra o Approval Gateway (Fase 1) como Application no Authentik (auth.rpa4all.com).

Uso:
    python3 tools/authentik_management/register_governance_app.py [--dry-run]

Variáveis de ambiente:
    AUTHENTIK_URL   — default: https://auth.rpa4all.com
    AUTHENTIK_TOKEN — token de API do Authentik

Executar quando:
    - Fase 1 for implantada (approval_gateway.service subir)
    - Para atualizar a launch_url após mudança de porta/host
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

AUTHENTIK_URL   = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.environ.get("AUTHENTIK_TOKEN", "")

# ── Configurações da aplicação no Authentik ───────────────────────────────
# Atualizar LAUNCH_URL quando a porta/host do gateway mudar
LAUNCH_URL   = os.environ.get("GOVERNANCE_GATEWAY_URL", "http://192.168.15.2:8510")
APP_NAME     = "Agent Approval Gateway"
APP_SLUG     = "agent-approval-gateway"
APP_DESC     = (
    "Gateway de aprovação humana para ações dos agentes do homelab. "
    "Agentes declaram intenções; humano aprova/rejeita via Telegram ou neste painel. "
    "Parte do Agent Governance Layer — Fase 1."
)
APP_ICON     = "pf-icon pf-icon-security"

# Apps adicionais a registrar nas próximas fases
FUTURE_APPS: list[dict] = [
    {
        "name": "Mem0 Memory Dashboard",
        "slug": "mem0-memory-dashboard",
        "url_env": "MEM0_URL",
        "url_default": "http://192.168.15.2:8511",
        "description": "Dashboard da memória compartilhada dos agentes (Fase 2). Busca semântica sobre git, wiki e action journal.",
        "phase": 2,
    },
    {
        "name": "Agent Journal (Grafana)",
        "slug": "agent-journal-grafana",
        "url_env": "GRAFANA_URL",
        "url_default": "http://192.168.15.2:3000/d/agent-governance",
        "description": "Dashboard Grafana do Action Journal — histórico de ações, aprovações e resultados por agente.",
        "phase": 2,
    },
]


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Executa chamadas na API do Authentik."""
    if not AUTHENTIK_TOKEN:
        raise RuntimeError("AUTHENTIK_TOKEN não configurado. Exporte a variável antes de executar.")
    url = f"{AUTHENTIK_URL}/api/v3{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} em {path}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha ao conectar no Authentik: {exc}") from exc


def _existing_app(slug: str) -> dict[str, Any] | None:
    result = _request("GET", f"/core/applications/?slug={slug}")
    items = result.get("results", [])
    return items[0] if items else None


def _upsert_app(name: str, slug: str, launch_url: str, description: str) -> tuple[str, str]:
    payload = {
        "name": name,
        "slug": slug,
        "meta_launch_url": launch_url,
        "meta_description": description,
        "policy_engine_mode": "any",
    }
    current = _existing_app(slug)
    if current:
        _request("PATCH", f"/core/applications/{current['pk']}/", payload)
        return str(current["pk"]), "updated"
    created = _request("POST", "/core/applications/", payload)
    return str(created["pk"]), "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra Approval Gateway no Authentik.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que faria sem executar.")
    parser.add_argument("--future", action="store_true", help="Também lista apps das Fases 2+ (apenas informativo).")
    args = parser.parse_args()

    print(f"Authentik: {AUTHENTIK_URL}")
    print(f"App:       {APP_NAME}")
    print(f"Slug:      {APP_SLUG}")
    print(f"URL:       {LAUNCH_URL}")
    print()

    if args.dry_run:
        print("[DRY-RUN] Nenhuma alteração será feita.")
        print(f"  → Criaria/atualizaria aplicação '{APP_NAME}' ({APP_SLUG}) apontando para {LAUNCH_URL}")
        if args.future:
            print("\nApps das Fases 2+ (a registrar no futuro):")
            for app in FUTURE_APPS:
                url = os.environ.get(app["url_env"], app["url_default"])
                print(f"  Fase {app['phase']}: {app['name']} → {url}")
        return 0

    try:
        pk, action = _upsert_app(APP_NAME, APP_SLUG, LAUNCH_URL, APP_DESC)
        print(f"✓ Aplicação '{APP_NAME}' {action} (pk={pk})")
        print(f"  Acesse em: {AUTHENTIK_URL}/if/launcher/")
        print()
        print("Próximos passos:")
        print("  1. Abrir auth.rpa4all.com → Applications → verificar atalho")
        print("  2. Após Fase 2: rodar novamente com --future para registrar Mem0 e Grafana")
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
