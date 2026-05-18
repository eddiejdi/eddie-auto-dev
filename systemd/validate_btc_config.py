#!/usr/bin/env python3
"""Valida config.json do BTC Trading Agent antes de iniciar o serviço.

Protege contra incidentes como GPT-5.1 (2026-03-05) que alterou dry_run.
Usado como ExecStartPre no systemd.
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from btc_trading_agent.profile_rules import validate_profile_for_symbol

BASE_DIR = Path("/apps/crypto-trader/trading/btc_trading_agent")


def resolve_config_path(argv: list[str] | None = None) -> Path:
    args = argv if argv is not None else sys.argv[1:]
    config_name = args[0] if args else os.environ.get("COIN_CONFIG_FILE", "config.json")
    candidate = Path(config_name)
    return candidate if candidate.is_absolute() else BASE_DIR / candidate


def validate_config_payload(config: dict, *, config_name: str) -> list[str]:
    errors: list[str] = []

    if "dry_run" not in config:
        errors.append("campo dry_run ausente")
    elif not isinstance(config["dry_run"], bool):
        errors.append(
            f"dry_run deve ser bool, encontrado {type(config['dry_run']).__name__}"
        )

    if "symbol" not in config:
        errors.append("campo symbol ausente")
    else:
        try:
            validate_profile_for_symbol(
                config["symbol"],
                config.get("profile", "default"),
                config_name=config_name,
            )
        except ValueError as exc:
            errors.append(str(exc))

    if "risk_management" not in config:
        errors.append("campo risk_management ausente (proteção removida?)")

    if "max_daily_loss" not in config:
        errors.append("campo max_daily_loss ausente")

    if "max_daily_trades" not in config:
        errors.append("campo max_daily_trades ausente")

    if "notifications" not in config:
        errors.append("campo notifications ausente (proteção removida?)")

    return errors


def main() -> int:
    """Valida campos obrigatórios do config.json."""
    config_path = resolve_config_path()
    try:
        c = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERRO: {config_path.name} inválido: {e}", file=sys.stderr)
        return 1

    errors = validate_config_payload(c, config_name=config_path.name)

    if errors:
        print(f"ERRO {config_path.name}: {errors}", file=sys.stderr)
        return 1

    print(
        f"Config OK: file={config_path.name}, dry_run={c['dry_run']}, "
        f"symbol={c.get('symbol', '?')}, profile={c.get('profile', 'default')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
