"""Client para consumir dados do Secrets Agent.

Exemplo:
  client = SecretsAgentClient("http://localhost:8088", api_key="...")
  secret = client.get_secret("eddie-jira-credentials")
"""
import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SecretsAgentClient:
    """Cliente para acessar o Secrets Agent."""
    
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
    
    def get_secret(self, item_id: str) -> Optional[str]:
        """Retorna o valor (senha/token) de um secret."""
        try:
            resp = self.client.get(
                f"{self.base_url}/secrets/{item_id}",
                headers={"X-API-KEY": self.api_key}
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("value")
        except Exception as e:
            logger.warning(f"SecretsAgent get_secret({item_id}) failed: {e}")
            return None
    
    def get_secret_field(self, item_id: str, field_name: str) -> Optional[str]:
        """Retorna um campo específico de um item do BW (ex: 'JIRA_API_TOKEN' do item 'eddie-jira-credentials')."""
        try:
            resp = self.client.get(
                f"{self.base_url}/secrets/{item_id}",
                headers={"X-API-KEY": self.api_key}
            )
            resp.raise_for_status()
            data = resp.json()
            # Assume que o valor é um JSON com campos
            import json
            val = data.get("value", "")
            if isinstance(val, str):
                try:
                    obj = json.loads(val)
                    return obj.get(field_name)
                except:
                    pass
            return val
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
