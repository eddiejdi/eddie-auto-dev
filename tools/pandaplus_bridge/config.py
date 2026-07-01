"""Configuração do bridge PandaPlus ↔ Telegram.

Lê variáveis de ambiente com defaults seguros. Em produção, valores sensíveis
(token Telegram, tokens Tuya) vêm do Secrets Agent ou do arquivo .storage
do Home Assistant.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BridgeConfig:
    """Configuração imutável do bridge.

    Attributes:
        device_id: ID Tuya da fechadura PandaPlus.
        ha_storage_path: Caminho para core.config_entries do Home Assistant.
        tuya_client_id: Client ID da integração Tuya do HA (constante pública).
        telegram_bot_token: Token do bot Telegram (sender).
        telegram_chat_id: Chat ID para enviar notificações.
        allowed_user_ids: Conjunto de user_id Telegram autorizados a aprovar.
        observe_only: Se True, NÃO envia reply_unlock_request (modo segurança).
        reply_listen_host: Host HTTP para receber decisões.
        reply_listen_port: Porta HTTP para receber decisões.
        database_url: URL Postgres para auditoria (opcional).
        request_ttl_seconds: TTL de cada pedido pendente.
    """

    device_id: str
    ha_storage_path: Path
    tuya_client_id: str = "HA_3y9q4ak7g4ephrvke"
    telegram_bot_token: str = ""
    telegram_chat_id: int = 0
    allowed_user_ids: frozenset[int] = field(default_factory=frozenset)
    observe_only: bool = True
    reply_listen_host: str = "127.0.0.1"
    reply_listen_port: int = 8590
    database_url: str = ""
    request_ttl_seconds: int = 90

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        """Carrega configuração de variáveis de ambiente.

        Returns:
            BridgeConfig validada.

        Raises:
            ValueError: Se variáveis obrigatórias estiverem ausentes.
        """
        device_id = os.environ.get("PANDAPLUS_DEVICE_ID", "").strip()
        if not device_id:
            raise ValueError("PANDAPLUS_DEVICE_ID é obrigatório")

        ha_storage = os.environ.get(
            "PANDAPLUS_HA_STORAGE",
            "/config/.storage/core.config_entries",
        )

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN é obrigatório")

        chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID", "0").strip()
        try:
            chat_id = int(chat_id_raw)
        except ValueError as exc:
            raise ValueError(f"TELEGRAM_CHAT_ID inválido: {chat_id_raw!r}") from exc
        if chat_id == 0:
            raise ValueError("TELEGRAM_CHAT_ID é obrigatório e não pode ser zero")

        allowed_raw = os.environ.get("PANDAPLUS_ALLOWED_USERS", "").strip()
        if allowed_raw:
            try:
                allowed = frozenset(
                    int(x) for x in allowed_raw.split(",") if x.strip()
                )
            except ValueError as exc:
                raise ValueError(
                    f"PANDAPLUS_ALLOWED_USERS inválido: {allowed_raw!r}"
                ) from exc
        else:
            allowed = frozenset({chat_id})  # default: dono do chat

        observe_only_raw = os.environ.get("PANDAPLUS_OBSERVE_ONLY", "1").strip()
        observe_only = observe_only_raw.lower() not in ("0", "false", "no", "off")

        return cls(
            device_id=device_id,
            ha_storage_path=Path(ha_storage),
            tuya_client_id=os.environ.get(
                "PANDAPLUS_TUYA_CLIENT_ID", "HA_3y9q4ak7g4ephrvke"
            ),
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            allowed_user_ids=allowed,
            observe_only=observe_only,
            reply_listen_host=os.environ.get(
                "PANDAPLUS_REPLY_HOST", "127.0.0.1"
            ),
            reply_listen_port=int(
                os.environ.get("PANDAPLUS_REPLY_PORT", "8590")
            ),
            database_url=os.environ.get("DATABASE_URL", ""),
            request_ttl_seconds=int(
                os.environ.get("PANDAPLUS_REQUEST_TTL", "90")
            ),
        )


def load_tuya_tokens(storage_path: Path) -> dict:
    """Lê tokens Tuya do core.config_entries do Home Assistant.

    Args:
        storage_path: Caminho para core.config_entries.

    Returns:
        Dict com keys: endpoint, terminal_id, user_code, token_info.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        KeyError: Se não houver entry Tuya configurada.
    """
    if not storage_path.exists():
        raise FileNotFoundError(f"HA storage não encontrado: {storage_path}")

    raw = json.loads(storage_path.read_text(encoding="utf-8"))
    entries = raw.get("data", {}).get("entries", [])
    tuya_entries = [e for e in entries if e.get("domain") == "tuya"]
    if not tuya_entries:
        raise KeyError("Nenhuma entry Tuya em core.config_entries")

    data = tuya_entries[0].get("data", {})
    required = {"endpoint", "terminal_id", "user_code", "token_info"}
    missing = required - set(data.keys())
    if missing:
        raise KeyError(f"Entry Tuya incompleta, faltam: {missing}")
    return data
