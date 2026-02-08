"""
Atlassian Confluence Cloud REST API Client.
Conecta ao Confluence em rpa4all.atlassian.net.

Documentação Atlassian REST API:
  https://developer.atlassian.com/cloud/confluence/rest/v1/intro/
  https://developer.atlassian.com/cloud/confluence/rest/v2/intro/

Usa as mesmas credenciais do Jira (Basic Auth: email + API token).
"""
import logging
from typing import Dict, List, Optional, Any

import httpx

from .atlassian_client import get_jira_config

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """
    Client para Atlassian Confluence Cloud REST API.
    Autenticação via Basic Auth (email + API token) — mesma do Jira.
    """

    def __init__(self, url: str = None, email: str = None, api_token: str = None):
        config = get_jira_config()
        self.base_url = (url or config["url"]).rstrip("/")
        self.email = email or config["email"]
        self.api_token = api_token or config["api_token"]

        if not self.api_token:
            logger.warning("⚠️  API_TOKEN não configurado — Confluence desabilitado")

        from base64 import b64encode
        creds = b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=30, headers=self.headers)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token)

    async def close(self):
        await self.client.aclose()

    # ═══════════════════════════ Helpers ══════════════════════════════════════

    async def _get(self, path: str, params: Dict = None) -> Dict:
        url = f"{self.base_url}/wiki/rest/api{path}"
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _get_v2(self, path: str, params: Dict = None) -> Dict:
        url = f"{self.base_url}/wiki/api/v2{path}"
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: Dict = None) -> Dict:
        url = f"{self.base_url}/wiki/rest/api{path}"
        resp = await self.client.post(url, json=data or {})
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}

    async def _put(self, path: str, data: Dict = None) -> Dict:
        url = f"{self.base_url}/wiki/rest/api{path}"
        resp = await self.client.put(url, json=data or {})
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}

    async def _delete(self, path: str) -> Dict:
        url = f"{self.base_url}/wiki/rest/api{path}"
        resp = await self.client.delete(url)
        resp.raise_for_status()
        return {"status": resp.status_code}

    # ═══════════════════════════ Spaces ═══════════════════════════════════════

    async def list_spaces(self, limit: int = 25) -> List[Dict]:
        """Lista todos os espaços Confluence."""
        data = await self._get("/space", {"limit": limit})
        return data.get("results", [])

    async def get_space(self, space_key: str) -> Dict:
        """Retorna detalhes de um espaço."""
        return await self._get(f"/space/{space_key}", {"expand": "homepage,description.plain"})

    async def create_space(self, key: str, name: str, description: str = "") -> Dict:
        """Cria um novo espaço Confluence."""
        payload = {
            "key": key,
            "name": name,
        }
        if description:
            payload["description"] = {
                "plain": {
                    "value": description,
                    "representation": "plain"
                }
            }
        return await self._post("/space", payload)

    # ═══════════════════════════ Pages ════════════════════════════════════════

    async def get_page(self, page_id: str, expand: str = "body.storage,version") -> Dict:
        """Retorna uma página por ID."""
        return await self._get(f"/content/{page_id}", {"expand": expand})

    async def get_page_by_title(self, space_key: str, title: str) -> Optional[Dict]:
        """Busca página por título no espaço."""
        data = await self._get("/content", {
            "spaceKey": space_key,
            "title": title,
            "expand": "version,body.storage",
        })
        results = data.get("results", [])
        return results[0] if results else None

    async def create_page(
        self,
        space_key: str,
        title: str,
        body_html: str,
        parent_id: str = None,
    ) -> Dict:
        """Cria uma nova página no Confluence.
        
        Args:
            space_key: Chave do espaço (ex: 'EA')
            title: Título da página
            body_html: Conteúdo em Storage Format (XHTML)
            parent_id: ID da página pai (opcional, default=homepage)
        """
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage"
                }
            }
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        return await self._post("/content", payload)

    async def update_page(
        self,
        page_id: str,
        title: str,
        body_html: str,
        version_number: int = None,
    ) -> Dict:
        """Atualiza uma página existente.
        
        Se version_number não for passado, busca versão atual automaticamente.
        """
        if not version_number:
            current = await self.get_page(page_id, expand="version")
            version_number = current["version"]["number"]

        payload = {
            "type": "page",
            "title": title,
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage"
                }
            },
            "version": {"number": version_number + 1}
        }
        return await self._put(f"/content/{page_id}", payload)

    async def delete_page(self, page_id: str) -> Dict:
        """Deleta uma página."""
        return await self._delete(f"/content/{page_id}")

    async def get_child_pages(self, page_id: str, limit: int = 50) -> List[Dict]:
        """Lista páginas filhas de uma página."""
        data = await self._get(
            f"/content/{page_id}/child/page",
            {"limit": limit, "expand": "version"}
        )
        return data.get("results", [])

    async def get_space_pages(self, space_key: str, limit: int = 100) -> List[Dict]:
        """Lista todas as páginas de um espaço."""
        data = await self._get("/content", {
            "spaceKey": space_key,
            "type": "page",
            "limit": limit,
            "expand": "version,ancestors",
        })
        return data.get("results", [])

    # ═══════════════════════════ Search ═══════════════════════════════════════

    async def search(self, cql: str, limit: int = 25) -> List[Dict]:
        """Busca no Confluence usando CQL (Confluence Query Language).
        
        Exemplos CQL:
            space = EA AND type = page
            text ~ "check-in" AND space = EA
            ancestor = 295076 AND type = page
        """
        data = await self._get("/search", {"cql": cql, "limit": limit})
        return data.get("results", [])

    # ═══════════════════════════ Labels ═══════════════════════════════════════

    async def add_labels(self, page_id: str, labels: List[str]) -> Dict:
        """Adiciona labels a uma página."""
        payload = [{"prefix": "global", "name": label} for label in labels]
        return await self._post(f"/content/{page_id}/label", payload)

    async def get_labels(self, page_id: str) -> List[Dict]:
        """Lista labels de uma página."""
        data = await self._get(f"/content/{page_id}/label")
        return data.get("results", [])

    # ═══════════════════════════ Attachments ══════════════════════════════════

    async def get_attachments(self, page_id: str) -> List[Dict]:
        """Lista attachments de uma página."""
        data = await self._get(
            f"/content/{page_id}/child/attachment",
            {"expand": "version"}
        )
        return data.get("results", [])

    async def upload_attachment(
        self,
        page_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        comment: str = "",
    ) -> Dict:
        """Upload de attachment para uma página.
        
        Útil para upload de diagramas draw.io, imagens, etc.
        """
        url = f"{self.base_url}/wiki/rest/api/content/{page_id}/child/attachment"
        headers = {
            "Authorization": self.headers["Authorization"],
            "X-Atlassian-Token": "nocheck",
        }
        files = {"file": (filename, content, content_type)}
        data = {}
        if comment:
            data["comment"] = comment

        # httpx multipart upload
        resp = await self.client.post(
            url,
            headers={"Authorization": self.headers["Authorization"],
                     "X-Atlassian-Token": "nocheck"},
            files=files,
            data=data,
        )
        resp.raise_for_status()
        return resp.json()

    # ═══════════════════════════ Comments ═════════════════════════════════════

    async def get_comments(self, page_id: str) -> List[Dict]:
        """Lista comentários de uma página."""
        data = await self._get(
            f"/content/{page_id}/child/comment",
            {"expand": "body.storage"}
        )
        return data.get("results", [])

    async def add_comment(self, page_id: str, body_html: str) -> Dict:
        """Adiciona comentário a uma página."""
        payload = {
            "type": "comment",
            "container": {"id": page_id, "type": "page"},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage"
                }
            }
        }
        return await self._post("/content", payload)

    # ═══════════════════════════ Properties ═══════════════════════════════════

    async def get_page_property(self, page_id: str, key: str) -> Optional[Dict]:
        """Lê uma propriedade de página (útil para metadados draw.io)."""
        try:
            return await self._get(f"/content/{page_id}/property/{key}")
        except Exception:
            return None

    async def set_page_property(self, page_id: str, key: str, value: Any) -> Dict:
        """Define uma propriedade de página."""
        existing = await self.get_page_property(page_id, key)
        if existing:
            # Update
            payload = {
                "key": key,
                "value": value,
                "version": {"number": existing["version"]["number"] + 1}
            }
            return await self._put(f"/content/{page_id}/property/{key}", payload)
        else:
            # Create
            payload = {"key": key, "value": value}
            return await self._post(f"/content/{page_id}/property", payload)


# ─── Singleton ────────────────────────────────────────────────────────────────

_confluence_client: Optional[ConfluenceClient] = None


def get_confluence_client() -> ConfluenceClient:
    """Singleton do ConfluenceClient."""
    global _confluence_client
    if _confluence_client is None:
        _confluence_client = ConfluenceClient()
    return _confluence_client
