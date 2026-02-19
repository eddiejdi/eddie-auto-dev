"""Client para consumir dados do Secrets Agent.

Exemplo:
  client = SecretsAgentClient("http://localhost:8088", api_key="...")
  secret = client.get_secret("eddie-jira-credentials")
  local  = client.get_local_secret("eddie/telegram_bot_token", field="token")
"""
import httpx
import logging
from typing import Optional, Dict, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class SecretsAgentClient:
    """Cliente para acessar o Secrets Agent.
    
    Resolução de secrets:
      1. Tenta endpoint local (/secrets/local/{name}?field=password)
      2. Fallback para Bitwarden (/secrets/{item_id})
    """
    
    def __init__(self, base_url: str = "http://localhost:8088", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=10)
    
    def list_secrets(self) -> Optional[Dict[str, Any]]:
        """Lista títulos dos secrets disponíveis."""
        try:
            resp = self.client.get(f"{self.base_url}/secrets")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"SecretsAgent list_secrets failed: {e}")
            return None
    
    def get_local_secret(self, name: str, field: str = "password") -> Optional[str]:
        """Busca um secret armazenado localmente no Secrets Agent."""
        try:
            encoded_name = quote(name, safe="")
            resp = self.client.get(
                f"{self.base_url}/secrets/local/{encoded_name}",
                params={"field": field},
                headers={"X-API-KEY": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("value")
        except Exception as e:
            logger.debug(f"SecretsAgent get_local_secret({name}, {field}) failed: {e}")
            return None
    
    def get_secret(self, item_id: str, field: str = "password") -> Optional[str]:
        """Retorna o valor de um secret (tenta local primeiro, depois Bitwarden)."""
        # 1. Tenta endpoint local
        val = self.get_local_secret(item_id, field=field)
        if val:
            return val
        # 2. Fallback: endpoint Bitwarden
        try:
            resp = self.client.get(
                f"{self.base_url}/secrets/{item_id}",
                headers={"X-API-KEY": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("value")
        except Exception as e:
            logger.warning(f"SecretsAgent get_secret({item_id}) failed: {e}")
            return None
    
    def get_secret_field(self, item_id: str, field_name: str) -> Optional[str]:
        """Retorna um campo específico de um item (local ou BW)."""
        # 1. Tenta local com field_name direto
        val = self.get_local_secret(item_id, field=field_name)
        if val:
            return val
        # 2. Fallback: BW endpoint (valor pode ser JSON com campos)
        try:
            resp = self.client.get(
                f"{self.base_url}/secrets/{item_id}",
                headers={"X-API-KEY": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            import json
            raw = data.get("value", "")
            if isinstance(raw, str):
                try:
                    obj = json.loads(raw)
                    return obj.get(field_name)
                except Exception:
                    pass
            return raw
        except Exception as e:
            logger.warning(f"SecretsAgent get_secret_field({item_id}, {field_name}) failed: {e}")
            return None
    
    def close(self):
        """Fecha a conexão."""
        self.client.close()


def get_secrets_agent_client() -> SecretsAgentClient:
    """Factory para obter client do Secrets Agent com config de env vars."""
    import os
    base_url = os.environ.get("SECRETS_AGENT_URL", "http://localhost:8088")
    api_key = os.environ.get("SECRETS_AGENT_API_KEY", "")
    return SecretsAgentClient(base_url, api_key)
