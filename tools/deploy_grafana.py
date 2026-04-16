#!/usr/bin/env python3
"""Deploy e consulta de dashboards Grafana via API.

Uso:
  python3 tools/deploy_grafana.py deploy --dashboard grafana/dashboards/btc_trading_monitor.json
  python3 tools/deploy_grafana.py export --uid btc-trading-monitor
  python3 tools/deploy_grafana.py query --uid btc-trading-monitor --panel 96
  python3 tools/deploy_grafana.py list
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("deploy_grafana")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3002")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASS = os.getenv("GRAFANA_PASS", "")
# Service account token (prefixo glsa_) — tem precedência sobre GRAFANA_USER/PASS
GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN", "")

# Campos que variam a cada save e não devem ser versionados
_VOLATILE_FIELDS = ("version", "iteration", "id")


# ---------------------------------------------------------------------------
# Helpers HTTP
# ---------------------------------------------------------------------------


def _auth_header() -> str:
    """Retorna header de autenticação: Bearer token (service account) ou Basic Auth."""
    if GRAFANA_TOKEN:
        return f"Bearer {GRAFANA_TOKEN}"
    import base64
    token = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()
    return f"Basic {token}"


def _request(method: str, path: str, body: Any | None = None) -> Any:
    """Executa request HTTP contra a API do Grafana.

    Args:
        method: Verbo HTTP (GET, POST, PUT, DELETE).
        path: Caminho relativo da API (ex: /api/dashboards/uid/foo).
        body: Objeto Python serializado como JSON no corpo da requisição.

    Returns:
        Objeto Python desserializado da resposta JSON.

    Raises:
        SystemExit: Em caso de erro HTTP.
    """
    url = f"{GRAFANA_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()[:300]
        log.error("HTTP %d %s → %s", exc.code, url, body_text)
        sys.exit(1)
    except urllib.error.URLError as exc:
        log.error("Não foi possível conectar ao Grafana em %s: %s", GRAFANA_URL, exc.reason)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------


def cmd_deploy(dashboard_path: Path, folder_uid: str | None = None) -> None:
    """Faz deploy de um dashboard JSON para o Grafana.

    Args:
        dashboard_path: Caminho para o arquivo JSON do dashboard.
        folder_uid: UID da pasta no Grafana (None = pasta padrão).
    """
    if not dashboard_path.exists():
        log.error("Arquivo não encontrado: %s", dashboard_path)
        sys.exit(1)

    dash = json.loads(dashboard_path.read_text(encoding="utf-8"))

    # Suporta tanto o JSON limpo (só dashboard) quanto o envelope completo
    if "dashboard" in dash:
        dash = dash["dashboard"]

    # Remove campos voláteis para evitar conflito de versão
    for field in _VOLATILE_FIELDS:
        dash.pop(field, None)

    payload: dict[str, Any] = {
        "dashboard": dash,
        "overwrite": True,
        "message": f"deploy via tools/deploy_grafana.py — {dashboard_path.name}",
    }
    if folder_uid:
        payload["folderUid"] = folder_uid

    result = _request("POST", "/api/dashboards/db", payload)
    if result.get("status") == "success":
        log.info("✅ Dashboard '%s' deployado → %s%s", dash.get("title"), GRAFANA_URL, result.get("url", ""))
    else:
        log.error("Falha no deploy: %s", result)
        sys.exit(1)


def cmd_export(uid: str, output: Path | None = None) -> None:
    """Exporta dashboard do Grafana para um arquivo JSON versionável.

    Args:
        uid: UID do dashboard no Grafana.
        output: Caminho de saída (None imprime no stdout).
    """
    data = _request("GET", f"/api/dashboards/uid/{uid}")
    dash = data.get("dashboard", data)

    # Remove campos voláteis
    for field in _VOLATILE_FIELDS:
        dash.pop(field, None)

    content = json.dumps(dash, indent=2, ensure_ascii=False)
    if output:
        output.write_text(content, encoding="utf-8")
        log.info("✅ Exportado para %s", output)
    else:
        print(content)


def cmd_list() -> None:
    """Lista todos os dashboards disponíveis no Grafana."""
    dashboards = _request("GET", "/api/search?type=dash-db&limit=100")
    if not dashboards:
        print("Nenhum dashboard encontrado.")
        return
    header = f"{'UID':<35} {'Título':<50} {'Pasta'}"
    print(header)
    print("-" * len(header))
    for d in dashboards:
        print(f"{d.get('uid',''):<35} {d.get('title',''):<50} {d.get('folderTitle','General')}")


def cmd_query(uid: str, panel_id: int | None = None) -> None:
    """Exibe informações de painéis de um dashboard.

    Args:
        uid: UID do dashboard.
        panel_id: ID do painel específico (None mostra todos).
    """
    data = _request("GET", f"/api/dashboards/uid/{uid}")
    panels = data.get("dashboard", {}).get("panels", [])

    if not panels:
        print("Nenhum painel encontrado.")
        return

    for panel in panels:
        pid = panel.get("id")
        if panel_id is not None and pid != panel_id:
            continue
        title = panel.get("title", "?")
        targets = panel.get("targets", [])
        print(f"\n{'─'*60}")
        print(f"[{pid}] {title}")
        for t in targets:
            sql = t.get("rawSql", "")
            expr = t.get("expr", "")
            if sql:
                print(f"  SQL: {sql.strip()[:300]}")
            if expr:
                print(f"  PromQL: {expr.strip()[:300]}")
        if not targets:
            print("  (sem query)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deploy e consulta de dashboards Grafana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", default=GRAFANA_URL, help="URL base do Grafana")
    parser.add_argument("--user", default=GRAFANA_USER, help="Usuário admin")
    parser.add_argument("--pass", dest="password", default=GRAFANA_PASS, help="Senha admin")
    parser.add_argument("--token", default=GRAFANA_TOKEN, help="Service account token (glsa_…) — tem precedência sobre usuário/senha")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # deploy
    p_deploy = sub.add_parser("deploy", help="Faz deploy de um dashboard JSON")
    p_deploy.add_argument("--dashboard", required=True, type=Path, help="Caminho do arquivo JSON")
    p_deploy.add_argument("--folder-uid", default=None, help="UID da pasta no Grafana")

    # export
    p_export = sub.add_parser("export", help="Exporta dashboard do Grafana para arquivo JSON")
    p_export.add_argument("--uid", required=True, help="UID do dashboard")
    p_export.add_argument("--output", type=Path, default=None, help="Arquivo de saída (padrão: stdout)")

    # list
    sub.add_parser("list", help="Lista dashboards disponíveis")

    # query
    p_query = sub.add_parser("query", help="Exibe queries/painéis de um dashboard")
    p_query.add_argument("--uid", required=True, help="UID do dashboard")
    p_query.add_argument("--panel", type=int, default=None, help="ID do painel específico")

    return parser


def main() -> None:
    """Ponto de entrada principal da ferramenta."""
    parser = _build_parser()
    args = parser.parse_args()

    # Aplica parâmetros de conexão
    global GRAFANA_URL, GRAFANA_USER, GRAFANA_PASS, GRAFANA_TOKEN
    GRAFANA_URL = args.url
    GRAFANA_USER = args.user
    GRAFANA_PASS = args.password
    GRAFANA_TOKEN = args.token

    if not GRAFANA_TOKEN and not GRAFANA_PASS:
        log.error("Autenticação não configurada. Use --token (service account) ou --pass.")
        sys.exit(1)

    if args.cmd == "deploy":
        cmd_deploy(args.dashboard, args.folder_uid)
    elif args.cmd == "export":
        cmd_export(args.uid, args.output)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "query":
        cmd_query(args.uid, args.panel)


if __name__ == "__main__":
    main()
