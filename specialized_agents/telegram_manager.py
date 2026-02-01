import os
import json
from typing import Dict, Optional

from .telegram_client import TelegramClient, TelegramConfig


class TelegramManager:
    """Gerencia múltiplos bots do Telegram identificados por chaves.

    Busca configurações em /etc/eddie/telegram_bots.json ou na variável
    de ambiente `TELEGRAM_BOTS_JSON`.
    Formato esperado (JSON):
    {
      "agent_key": {"bot_token": "<token>", "chat_id": "<chat_id>"},
      "other": {"bot_token": "...", "chat_id": "..."}
    }
    """

    def __init__(self):
        self._clients: Dict[str, TelegramClient] = {}
        self._configs: Dict[str, Dict] = {}
        self._load_configs()

    def _load_configs(self):
        # Support either a plain JSON file or an openssl-encrypted file
        plain_path = os.getenv("TELEGRAM_BOTS_FILE", "/etc/eddie/telegram_bots.json")
        enc_path = plain_path + ".enc"
        raw = None

        # If encrypted file exists, try to decrypt using password from env
        if os.path.exists(enc_path):
            pwd = os.getenv("TELEGRAM_BOTS_PASS")
            if pwd:
                try:
                    import subprocess

                    p = subprocess.Popen(
                        [
                            "openssl",
                            "enc",
                            "-aes-256-cbc",
                            "-d",
                            "-salt",
                            "-pass",
                            f"pass:{pwd}",
                            "-in",
                            enc_path,
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    out, err = p.communicate(timeout=5)
                    if p.returncode == 0:
                        raw = out.decode("utf-8")
                except Exception:
                    raw = None
            # If decryption not attempted or failed, try reading the enc file as plain JSON
            if raw is None:
                try:
                    with open(enc_path, "r", encoding="utf-8") as f:
                        raw = f.read()
                except Exception:
                    raw = None

        # Fallback: read plain file
        if raw is None and os.path.exists(plain_path):
            try:
                with open(plain_path, "r", encoding="utf-8") as f:
                    raw = f.read()
            except Exception:
                raw = None

        if not raw:
            raw = os.getenv("TELEGRAM_BOTS_JSON")

        if not raw:
            return

        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                self._configs = data
        except Exception:
            self._configs = {}

    def get_client(self, key: Optional[str] = None) -> Optional[TelegramClient]:
        """Retorna um TelegramClient para a chave especificada.
        Se `key` for None, retorna um client padrão criado a partir de env.
        """
        if not key:
            return TelegramClient.from_env()

        if key in self._clients:
            return self._clients[key]

        cfg = self._configs.get(key)
        if not cfg:
            return None

        bot_token = cfg.get("bot_token") or cfg.get("token")
        chat_id = cfg.get("chat_id") or cfg.get("chat")
        if not bot_token or not chat_id:
            return None

        tcfg = TelegramConfig(bot_token=bot_token, chat_id=str(chat_id))
        client = TelegramClient(tcfg)
        self._clients[key] = client
        return client


# Module-level singleton
_manager: Optional[TelegramManager] = None


def get_telegram_manager() -> TelegramManager:
    global _manager
    if _manager is None:
        _manager = TelegramManager()
    return _manager
