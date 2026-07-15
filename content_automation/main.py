#!/usr/bin/env python3
"""Entrypoint — executa scheduler continuamente."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from content_automation.config import load_settings
from content_automation.logging_setup import log_event, setup_logging
from content_automation.scheduler import ContentScheduler


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automação de conteúdo viral com agenda diária.")
    parser.add_argument(
        "--settings",
        default=None,
        help="Caminho para settings.yaml (padrão: content_automation/settings.yaml)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa um ciclo e encerra (útil para testes/CI).",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Apenas planeja slots do dia sem processar fila.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Processa todos os pending, ignorando horário do slot.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = load_settings(args.settings)
    logs_dir = Path(settings["paths"]["logs_dir"])
    logger = setup_logging(logs_dir)

    scheduler = ContentScheduler(settings)
    poll = int(settings["scheduler"]["poll_interval_seconds"])

    log_event(
        logger,
        "scheduler_started",
        mode="once" if args.once else "daemon",
        poll_interval_seconds=poll,
    )

    if args.plan_only:
        planned = scheduler.plan_daily_slots()
        print(json.dumps([item.to_dict() for item in planned], indent=2, ensure_ascii=False))
        return 0

    while True:
        stats = scheduler.run_cycle(force=args.force)
        log_event(
            logger,
            "scheduler_cycle_complete",
            generated=stats.generated,
            published=stats.published,
            failed=stats.failed,
            duration_seconds=round(stats.duration_seconds, 2),
            errors=stats.errors,
        )
        if args.once:
            print(
                json.dumps(
                    {
                        "generated": stats.generated,
                        "published": stats.published,
                        "failed": stats.failed,
                        "duration_seconds": stats.duration_seconds,
                        "errors": stats.errors,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0 if stats.failed == 0 else 1
        time.sleep(poll)


if __name__ == "__main__":
    raise SystemExit(main())