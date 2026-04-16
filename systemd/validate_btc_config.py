#!/usr/bin/env python3
"""Valida config.json do BTC Trading Agent antes de iniciar o serviço.

Protege contra incidentes como GPT-5.1 (2026-03-05) que alterou dry_run.
Usado como ExecStartPre no systemd.
"""

import json
import sys
from pathlib import Path

CONFIG = Path("/apps/crypto-trader/trading/btc_trading_agent/config.json")


def main() -> int:
    """Valida campos obrigatórios do config.json."""
    try:
        c = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERRO: config.json inválido: {e}", file=sys.stderr)
        return 1

    errors: list[str] = []

    if "dry_run" not in c:
        errors.append("campo dry_run ausente")
    elif not isinstance(c["dry_run"], bool):
        errors.append(
            f"dry_run deve ser bool, encontrado {type(c['dry_run']).__name__}"
        )

    if "symbol" not in c:
        errors.append("campo symbol ausente")

    if "risk_management" not in c:
        errors.append("campo risk_management ausente (proteção removida?)")

    if "max_daily_loss" not in c:
        errors.append("campo max_daily_loss ausente")

    if "max_daily_trades" not in c:
        errors.append("campo max_daily_trades ausente")

    if "notifications" not in c:
        errors.append("campo notifications ausente (proteção removida?)")

    if errors:
        print(f"ERRO config.json: {errors}", file=sys.stderr)
        return 1

    print(f"Config OK: dry_run={c['dry_run']}, symbol={c.get('symbol', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
