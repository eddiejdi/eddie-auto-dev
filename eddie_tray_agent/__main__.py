#!/usr/bin/env python3
"""Eddie Tray Agent — entry point.

Usage:
    python -m eddie_tray_agent
    python eddie_tray_agent/__main__.py
"""
import logging
import sys

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("eddie_tray_agent.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger("eddie_tray_agent")


def main():
    logger.info("🚀 Iniciando Eddie Tray Agent v0.1.0")
    try:
        from eddie_tray_agent.app import EddieTrayApp
        app = EddieTrayApp()
        app.start()
    except KeyboardInterrupt:
        logger.info("👋 Interrompido pelo usuário")
    except Exception as exc:
        logger.error("💥 Erro fatal: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
