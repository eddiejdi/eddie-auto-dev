"""
Atlassian Jira Cloud REST API Client.
Conecta ao Jira real em rpa4all.atlassian.net.

Documentação Atlassian REST API v3:
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/

Credenciais via:
  - Env vars: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN
  - simple_vault: jira/url, jira/email, jira/api_token
"""
import os
import logging
from base64 import b64encode
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)

# ─── Resolver credenciais ─────────────────────────────────────────────────────

def _load_env_jira():
    """Carrega credenciais de .env.jira se existir."""
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env.jira")
    env_file = os.path.normpath(env_file)
    if os.path.isfile(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

_load_env_jira()


def _get_secret(name: str, env_key: str, default: str = "") -> str:
    """Resolve credencial: env var / .env.jira > simple_vault > default."""
    val = os.environ.get(env_key, "")
    if val:
        return val
    try:
        from tools.vault.secret_store import get_field
        secret = get_field(name)
        if secret:
            return secret
    except Exception:
        pass
    return default


def get_jira_config() -> Dict[str, str]:
    """Retorna configuração de conexão com Jira Cloud."""
    return {
        "url": _get_secret("jira/url", "JIRA_URL", "https://rpa4all.atlassian.net"),
        "email": _get_secret("jira/email", "JIRA_EMAIL", "edenilson.teixeira@rpa4all.com"),
        "api_token": _get_secret("jira/api_token", "JIRA_API_TOKEN", ""),
    }


# ─── Client ───────────────────────────────────────────────────────────────────

class JiraCloudClient:
    """
    Client para Atlassian Jira Cloud REST API v3.
    Autenticação via Basic Auth (email + API token).
    """

    def __init__(self, url: str = None, email: str = None, api_token: str = None):
        config = get_jira_config()
        self.base_url = (url or config["url"]).rstrip("/")
        self.email = email or config["email"]
        self.api_token = api_token or config["api_token"]

        if not self.api_token:
            logger.warning("⚠️  JIRA_API_TOKEN não configurado — operações Jira Cloud desabilitadas")

        # Basic Auth: base64(email:token)
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
        url = f"{self.base_url}/rest/api/3{path}"
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: Dict = None) -> Dict:
        url = f"{self.base_url}/rest/api/3{path}"
        resp = await self.client.post(url, json=data or {})
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}

    async def _put(self, path: str, data: Dict = None) -> Dict:
        url = f"{self.base_url}/rest/api/3{path}"
        resp = await self.client.put(url, json=data or {})
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}

    async def _delete(self, path: str) -> Dict:
        url = f"{self.base_url}/rest/api/3{path}"
        resp = await self.client.delete(url)
        resp.raise_for_status()
        return {"status": resp.status_code}

    # Agile API separada (prefix diferente)
    async def _agile_get(self, path: str, params: Dict = None) -> Dict:
        url = f"{self.base_url}/rest/agile/1.0{path}"
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _agile_post(self, path: str, data: Dict = None) -> Dict:
        url = f"{self.base_url}/rest/agile/1.0{path}"
        resp = await self.client.post(url, json=data or {})
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}

    # ═══════════════════════════ Myself ═══════════════════════════════════════

    async def myself(self) -> Dict:
        """Retorna dados do usuário autenticado."""
        return await self._get("/myself")

    async def server_info(self) -> Dict:
        """Retorna informações do servidor Jira."""
        return await self._get("/serverInfo")

    # ═══════════════════════════ Projects ═════════════════════════════════════

    async def list_projects(self) -> List[Dict]:
        """Lista todos os projetos acessíveis."""
        data = await self._get("/project/search")
        return data.get("values", [])

    async def get_project(self, key: str) -> Dict:
        """Retorna dados de um projeto."""
        return await self._get(f"/project/{key}")

    async def create_project(
        self, name: str, key: str, project_type: str = "software",
        template_key: str = "com.pyxis.greenhopper.jira:gh-simplified-scrum-classic",
        lead_account_id: str = None,
    ) -> Dict:
        """Cria um novo projeto."""
        payload = {
            "name": name,
            "key": key,
            "projectTypeKey": project_type,
            "projectTemplateKey": template_key,
        }
        if lead_account_id:
            payload["leadAccountId"] = lead_account_id
        return await self._post("/project", payload)

    # ═══════════════════════════ Issue Types ══════════════════════════════════

    async def get_issue_types(self, project_key: str = None) -> List[Dict]:
        """Lista tipos de issue disponíveis."""
        if project_key:
            data = await self._get(f"/project/{project_key}")
            return data.get("issueTypes", [])
        return await self._get("/issuetype")

    async def get_create_meta(self, project_key: str) -> Dict:
        """Metadados para criação de issues em um projeto."""
        return await self._get("/issue/createmeta", {
            "projectKeys": project_key,
            "expand": "projects.issuetypes.fields",
        })

    # ═══════════════════════════ Issues ════════════════════════════════════════

    async def create_issue(
        self, project_key: str, summary: str, issue_type: str = "Task",
        description: str = "", priority: str = "Medium",
        assignee_id: str = None, labels: List[str] = None,
        parent_key: str = None, story_points: int = None,
        epic_key: str = None,
    ) -> Dict:
        """
        Cria uma issue no Jira.

        issue_type: Task, Story, Bug, Epic, Sub-task
        priority: Highest, High, Medium, Low, Lowest
        """
        # Descrição em Atlassian Document Format (ADF)
        desc_adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}]
                }
            ] if description else []
        }

        fields: Dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "description": desc_adf,
            "priority": {"name": priority},
        }

        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}
        if labels:
            fields["labels"] = labels
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if story_points is not None:
            # Story points field varia por projeto; customfield_10016 é o padrão
            fields["customfield_10016"] = story_points

        return await self._post("/issue", {"fields": fields})

    async def get_issue(self, issue_key: str, fields: str = None) -> Dict:
        """Retorna uma issue por key (ex: RPA-1)."""
        params = {}
        if fields:
            params["fields"] = fields
        return await self._get(f"/issue/{issue_key}", params)

    async def update_issue(self, issue_key: str, fields: Dict) -> Dict:
        """Atualiza campos de uma issue."""
        return await self._put(f"/issue/{issue_key}", {"fields": fields})

    async def delete_issue(self, issue_key: str) -> Dict:
        return await self._delete(f"/issue/{issue_key}")

    async def search_issues(self, jql: str, fields: str = None,
                            max_results: int = 50) -> Dict:
        """
        Busca issues via JQL.
        
        Exemplos JQL:
          project = RPA AND assignee = currentUser() ORDER BY priority DESC
          project = RPA AND sprint in openSprints()
          project = RPA AND status = "In Progress"
        """
        payload: Dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
        }
        if fields:
            payload["fields"] = fields.split(",")
        else:
            # Default fields para o enhanced search endpoint (/search/jql)
            payload["fields"] = ["summary", "status", "issuetype", "priority",
                                 "labels", "assignee", "created", "updated",
                                 "parent", "description"]
        # Jira Cloud v3 migrou /search para /search/jql (410 Gone no antigo)
        try:
            return await self._post("/search/jql", payload)
        except Exception:
            # Fallback para API antiga caso funcione
            return await self._post("/search", payload)

    # ═══════════════════════════ Transitions ══════════════════════════════════

    async def get_transitions(self, issue_key: str) -> List[Dict]:
        """Lista transições disponíveis para uma issue."""
        data = await self._get(f"/issue/{issue_key}/transitions")
        return data.get("transitions", [])

    async def transition_issue(self, issue_key: str, transition_id: str,
                                comment: str = None) -> Dict:
        """Move issue para um novo status via transition."""
        payload: Dict[str, Any] = {
            "transition": {"id": transition_id}
        }
        if comment:
            payload["update"] = {
                "comment": [{
                    "add": {
                        "body": {
                            "type": "doc", "version": 1,
                            "content": [{"type": "paragraph",
                                         "content": [{"type": "text", "text": comment}]}]
                        }
                    }
                }]
            }
        return await self._post(f"/issue/{issue_key}/transitions", payload)

    async def move_issue_to_status(self, issue_key: str, target_status: str,
                                    comment: str = None) -> Dict:
        """
        Move issue para um status por nome (wrapper amigável).
        Ex: move_issue_to_status("RPA-1", "In Progress")
        """
        transitions = await self.get_transitions(issue_key)
        for t in transitions:
            if t["name"].lower() == target_status.lower() or \
               t.get("to", {}).get("name", "").lower() == target_status.lower():
                return await self.transition_issue(issue_key, t["id"], comment)
        available = [t["name"] for t in transitions]
        raise ValueError(f"Transição '{target_status}' não disponível. Disponíveis: {available}")

    # ═══════════════════════════ Assign ═══════════════════════════════════════

    async def assign_issue(self, issue_key: str, account_id: str = None) -> Dict:
        """Atribui issue a um usuário. account_id=None remove atribuição."""
        return await self._put(f"/issue/{issue_key}/assignee",
                                {"accountId": account_id})

    # ═══════════════════════════ Comments ═════════════════════════════════════

    async def add_comment(self, issue_key: str, body: str) -> Dict:
        """Adiciona comentário a uma issue."""
        payload = {
            "body": {
                "type": "doc", "version": 1,
                "content": [
                    {"type": "paragraph",
                     "content": [{"type": "text", "text": body}]}
                ]
            }
        }
        return await self._post(f"/issue/{issue_key}/comment", payload)

    async def get_comments(self, issue_key: str) -> List[Dict]:
        """Lista comentários de uma issue."""
        data = await self._get(f"/issue/{issue_key}/comment")
        return data.get("comments", [])

    # ═══════════════════════════ Worklogs ═════════════════════════════════════

    async def add_worklog(self, issue_key: str, time_spent: str,
                          comment: str = "", started: str = None) -> Dict:
        """
        Adiciona worklog a uma issue.
        
        time_spent: formato Jira — "2h", "30m", "1h 30m", "1d"
        started: ISO datetime (ex: "2026-02-08T10:00:00.000+0000")
        """
        payload: Dict[str, Any] = {
            "timeSpent": time_spent,
        }
        if comment:
            payload["comment"] = {
                "type": "doc", "version": 1,
                "content": [
                    {"type": "paragraph",
                     "content": [{"type": "text", "text": comment}]}
                ]
            }
        if started:
            payload["started"] = started
        return await self._post(f"/issue/{issue_key}/worklog", payload)

    async def get_worklogs(self, issue_key: str) -> List[Dict]:
        """Lista worklogs de uma issue."""
        data = await self._get(f"/issue/{issue_key}/worklog")
        return data.get("worklogs", [])

    # ═══════════════════════════ Sprints (Agile) ══════════════════════════════

    async def get_boards(self, project_key: str = None) -> List[Dict]:
        """Lista boards do projeto."""
        params = {}
        if project_key:
            params["projectKeyOrId"] = project_key
        data = await self._agile_get("/board", params)
        return data.get("values", [])

    async def get_sprints(self, board_id: int, state: str = None) -> List[Dict]:
        """
        Lista sprints de um board.
        state: active, future, closed
        """
        params = {}
        if state:
            params["state"] = state
        data = await self._agile_get(f"/board/{board_id}/sprint", params)
        return data.get("values", [])

    async def create_sprint(self, board_id: int, name: str, goal: str = "",
                            start_date: str = None, end_date: str = None) -> Dict:
        """Cria novo sprint."""
        payload = {
            "name": name,
            "originBoardId": board_id,
        }
        if goal:
            payload["goal"] = goal
        if start_date:
            payload["startDate"] = start_date
        if end_date:
            payload["endDate"] = end_date
        return await self._agile_post("/sprint", payload)

    async def start_sprint(self, sprint_id: int, start_date: str,
                           end_date: str) -> Dict:
        """Inicia um sprint."""
        payload = {
            "state": "active",
            "startDate": start_date,
            "endDate": end_date,
        }
        url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}"
        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def move_to_sprint(self, sprint_id: int, issue_keys: List[str]) -> Dict:
        """Move issues para um sprint."""
        payload = {"issues": issue_keys}
        return await self._agile_post(f"/sprint/{sprint_id}/issue", payload)

    async def get_sprint_issues(self, sprint_id: int) -> List[Dict]:
        """Lista issues de um sprint."""
        data = await self._agile_get(f"/sprint/{sprint_id}/issue")
        return data.get("issues", [])

    # ═══════════════════════════ Users / Assignable ═══════════════════════════

    async def search_users(self, query: str) -> List[Dict]:
        """Busca usuários pelo email ou nome."""
        return await self._get("/user/search", {"query": query})

    async def get_assignable_users(self, project_key: str) -> List[Dict]:
        """Lista usuários atribuíveis a issues de um projeto."""
        return await self._get("/user/assignable/search",
                                {"project": project_key})

    # ═══════════════════════════ Labels ════════════════════════════════════════

    async def get_labels(self) -> List[str]:
        """Lista todas as labels."""
        data = await self._get("/label")
        return data.get("values", [])

    # ═══════════════════════════ Priorities ════════════════════════════════════

    async def get_priorities(self) -> List[Dict]:
        """Lista prioridades disponíveis."""
        return await self._get("/priority")

    # ═══════════════════════════ Status ════════════════════════════════════════

    async def get_statuses(self, project_key: str = None) -> List[Dict]:
        """Lista statuses de um projeto ou globais."""
        if project_key:
            return await self._get(f"/project/{project_key}/statuses")
        return await self._get("/status")


# ─── Singleton ────────────────────────────────────────────────────────────────

_jira_client: Optional[JiraCloudClient] = None


def get_jira_cloud_client() -> JiraCloudClient:
    """Singleton do JiraCloudClient."""
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraCloudClient()
    return _jira_client
