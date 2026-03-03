#!/usr/bin/env python3
"""
Corrige regras de alerta do Grafana para tratar 'no data' como OK.

Quando Prometheus targets ficam offline, as alert rules do Grafana
tratam 'no data' como estado de alerta (Alerting), gerando falsos
positivos massivos enviados via Telegram.

Este script altera todas as regras para:
  - noDataState: "OK" (em vez de "Alerting")
  - execErrState: "OK" (em vez de "Alerting")

Uso:
  python3 tools/fix_grafana_nodata_alerts.py [--grafana-url URL] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

GRAFANA_URL = "http://localhost:3002"
GRAFANA_USER = "admin"
GRAFANA_PASS = "admin"


def get_alert_rules(base_url: str, auth: tuple[str, str]) -> list[dict[str, Any]]:
    """Busca todas as alert rules do Grafana via Provisioning API."""
    resp = requests.get(
        f"{base_url}/api/v1/provisioning/alert-rules",
        auth=auth,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def update_alert_rule(
    base_url: str,
    auth: tuple[str, str],
    rule: dict[str, Any],
    dry_run: bool = False,
) -> bool:
    """Atualiza uma alert rule para noDataState=OK e execErrState=OK."""
    uid = rule["uid"]
    title = rule.get("title", "?")
    current_no_data = rule.get("noDataState", "not set")
    current_exec_err = rule.get("execErrState", "not set")

    needs_fix = current_no_data != "OK" or current_exec_err != "OK"
    if not needs_fix:
        logger.info(f"  ✅ {title} — já está OK")
        return False

    logger.info(
        f"  🔧 {title} — noData={current_no_data}→OK, execErr={current_exec_err}→OK"
    )

    if dry_run:
        return True

    rule["noDataState"] = "OK"
    rule["execErrState"] = "OK"

    # Grafana Provisioning API PUT requer header X-Disable-Provenance
    headers = {
        "Content-Type": "application/json",
        "X-Disable-Provenance": "true",
    }

    resp = requests.put(
        f"{base_url}/api/v1/provisioning/alert-rules/{uid}",
        auth=auth,
        headers=headers,
        json=rule,
        timeout=15,
    )

    if resp.status_code == 200:
        logger.info(f"    ✅ Atualizado com sucesso")
        return True
    else:
        logger.error(f"    ❌ Erro {resp.status_code}: {resp.text[:200]}")
        return False


def main() -> None:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(description="Corrige noDataState das alert rules do Grafana")
    parser.add_argument("--grafana-url", default=GRAFANA_URL, help="URL do Grafana")
    parser.add_argument("--user", default=GRAFANA_USER, help="Usuário admin")
    parser.add_argument("--password", default=GRAFANA_PASS, help="Senha admin")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que seria alterado")
    args = parser.parse_args()

    auth = (args.user, args.password)
    base_url = args.grafana_url.rstrip("/")

    logger.info(f"Conectando ao Grafana: {base_url}")
    rules = get_alert_rules(base_url, auth)
    logger.info(f"Encontradas {len(rules)} alert rules\n")

    fixed = 0
    for rule in rules:
        if update_alert_rule(base_url, auth, rule, dry_run=args.dry_run):
            fixed += 1

    action = "seriam corrigidas" if args.dry_run else "corrigidas"
    logger.info(f"\n{'='*50}")
    logger.info(f"Total: {len(rules)} rules, {fixed} {action}")

    if args.dry_run and fixed > 0:
        logger.info("Execute sem --dry-run para aplicar as alterações.")


if __name__ == "__main__":
    main()
