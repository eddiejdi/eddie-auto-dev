"""
SmartLife Integration - Main Entry Point
"""

import asyncio
import signal
import sys
import os
from pathlib import Path

import structlog
import yaml

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import SmartLifeService
from src.interfaces import SmartLifeTelegramBot

logger = structlog.get_logger()


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Carrega configuração do arquivo YAML."""
    config_file = Path(config_path)

    if not config_file.exists():
        logger.warning(f"Config não encontrado: {config_path}. Usando valores padrão.")
        return {}

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Substituir variáveis de ambiente
    config = _expand_env_vars(config)

    return config


def _expand_env_vars(config: dict) -> dict:
    """Expande variáveis de ambiente no config."""
    if isinstance(config, dict):
        return {k: _expand_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_expand_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        var_name = config[2:-1]
        return os.environ.get(var_name, config)
    return config


async def main():
    """Função principal."""
    # Configurar logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger.info("=" * 50)
    logger.info("SmartLife Integration Service")
    logger.info("=" * 50)

    # Carregar configuração
    config = load_config()

    # Criar serviço principal
    service = SmartLifeService(config)

    # Criar bot Telegram (se configurado)
    telegram_bot = None
    if config.get("telegram", {}).get("enabled", True):
        token = config.get("telegram", {}).get("token")
        if token:
            telegram_bot = SmartLifeTelegramBot(
                token=token,
                smartlife_service=service,
                admin_ids=config.get("telegram", {}).get("admin_ids", []),
            )

    # Handler de shutdown
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Sinal de shutdown recebido...")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Iniciar serviço
        await service.start()

        # Iniciar bot Telegram
        if telegram_bot:
            await telegram_bot.start()

        logger.info("Serviço iniciado. Aguardando...")

        # Aguardar shutdown
        await shutdown_event.wait()

    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        raise

    finally:
        # Cleanup
        logger.info("Encerrando serviço...")

        if telegram_bot:
            await telegram_bot.stop()

        await service.stop()

        logger.info("Serviço encerrado.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
