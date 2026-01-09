"""
Cliente para integração com GitHub Agent
Permite que os agentes especializados interajam com GitHub
"""
import os
import json
import httpx
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from .config import GITHUB_AGENT_CONFIG


class GitHubAction(Enum):
    LIST_REPOS = "list_repos"
    GET_REPO = "get_repo"
    CREATE_REPO = "create_repo"
    LIST_ISSUES = "list_issues"
    CREATE_ISSUE = "create_issue"
    LIST_PRS = "list_prs"
    CREATE_PR = "create_pr"
    LIST_BRANCHES = "list_branches"
    CREATE_BRANCH = "create_branch"
    PUSH_CODE = "push_code"
    CLONE_REPO = "clone_repo"
    SEARCH_CODE = "search_code"
    LIST_COMMITS = "list_commits"
    GET_FILE = "get_file"
    UPDATE_FILE = "update_file"


@dataclass
class GitHubResult:
    success: bool
    action: str
    data: Dict[str, Any] = None
    error: str = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "action": self.action,
            "data": self.data,
            "error": self.error
        }


class GitHubAgentClient:
    """
    Cliente para comunicação com o GitHub Agent existente.
    Permite que agentes especializados realizem operações no GitHub.
    """
    
    def __init__(self, api_url: str = None, token: str = None):
        self.api_url = api_url or GITHUB_AGENT_CONFIG.get("api_url", "http://localhost:8080")
        self.token = token or GITHUB_AGENT_CONFIG.get("token") or os.getenv("GITHUB_TOKEN", "")
        self.client = httpx.AsyncClient(timeout=60.0)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None
    ) -> Dict[str, Any]:
        """Faz requisição para GitHub Agent"""
        url = f"{self.api_url}{endpoint}"
        try:
            response = await self.client.request(
                method,
                url,
                json=data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}
    
    async def execute(self, action: str, params: Dict = None) -> GitHubResult:
        """Executa ação no GitHub Agent"""
        params = params or {}
        
        try:
            result = await self._request("POST", "/api/execute", {
                "action": action,
                "params": params
            })
            
            if "error" in result:
                return GitHubResult(
                    success=False,
                    action=action,
                    error=result["error"]
                )
            
            return GitHubResult(
                success=True,
                action=action,
                data=result
            )
        except Exception as e:
            return GitHubResult(
                success=False,
                action=action,
                error=str(e)
            )
    
    # ================== Repositórios ==================
    
    async def list_repos(self, owner: str = None, org: str = None) -> GitHubResult:
        """Lista repositórios"""
        return await self.execute("list_repos", {"owner": owner, "org": org})
    
    async def get_repo(self, owner: str, repo: str) -> GitHubResult:
        """Obtém detalhes de repositório"""
        return await self.execute("get_repo", {"owner": owner, "repo": repo})
    
    async def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        language: str = None
    ) -> GitHubResult:
        """Cria novo repositório"""
        return await self.execute("create_repo", {
            "name": name,
            "description": description,
            "private": private,
            "language": language
        })
    
    async def clone_repo(
        self,
        owner: str,
        repo: str,
        destination: str = None
    ) -> GitHubResult:
        """Clona repositório"""
        return await self.execute("clone_repo", {
            "owner": owner,
            "repo": repo,
            "destination": destination
        })
    
    # ================== Branches ==================
    
    async def list_branches(self, owner: str, repo: str) -> GitHubResult:
        """Lista branches"""
        return await self.execute("list_branches", {"owner": owner, "repo": repo})
    
    async def create_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        from_branch: str = "main"
    ) -> GitHubResult:
        """Cria nova branch"""
        return await self.execute("create_branch", {
            "owner": owner,
            "repo": repo,
            "branch_name": branch_name,
            "from_branch": from_branch
        })
    
    # ================== Issues ==================
    
    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open"
    ) -> GitHubResult:
        """Lista issues"""
        return await self.execute("list_issues", {
            "owner": owner,
            "repo": repo,
            "state": state
        })
    
    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: List[str] = None
    ) -> GitHubResult:
        """Cria nova issue"""
        return await self.execute("create_issue", {
            "owner": owner,
            "repo": repo,
            "title": title,
            "body": body,
            "labels": labels or []
        })
    
    async def close_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int
    ) -> GitHubResult:
        """Fecha issue"""
        return await self.execute("close_issue", {
            "owner": owner,
            "repo": repo,
            "issue_number": issue_number
        })
    
    # ================== Pull Requests ==================
    
    async def list_prs(
        self,
        owner: str,
        repo: str,
        state: str = "open"
    ) -> GitHubResult:
        """Lista pull requests"""
        return await self.execute("list_prs", {
            "owner": owner,
            "repo": repo,
            "state": state
        })
    
    async def create_pr(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main"
    ) -> GitHubResult:
        """Cria pull request"""
        return await self.execute("create_pr", {
            "owner": owner,
            "repo": repo,
            "title": title,
            "body": body,
            "head": head,
            "base": base
        })
    
    # ================== Arquivos e Código ==================
    
    async def get_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main"
    ) -> GitHubResult:
        """Obtém conteúdo de arquivo"""
        return await self.execute("get_file", {
            "owner": owner,
            "repo": repo,
            "path": path,
            "ref": ref
        })
    
    async def update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: str = None
    ) -> GitHubResult:
        """Atualiza arquivo no repositório"""
        return await self.execute("update_file", {
            "owner": owner,
            "repo": repo,
            "path": path,
            "content": content,
            "message": message,
            "branch": branch,
            "sha": sha
        })
    
    async def push_code(
        self,
        owner: str,
        repo: str,
        files: Dict[str, str],
        message: str,
        branch: str = "main"
    ) -> GitHubResult:
        """Push de múltiplos arquivos"""
        return await self.execute("push_code", {
            "owner": owner,
            "repo": repo,
            "files": files,
            "message": message,
            "branch": branch
        })
    
    async def search_code(
        self,
        query: str,
        owner: str = None,
        repo: str = None,
        language: str = None
    ) -> GitHubResult:
        """Busca código"""
        params = {"query": query}
        if owner:
            params["owner"] = owner
        if repo:
            params["repo"] = repo
        if language:
            params["language"] = language
        
        return await self.execute("search_code", params)
    
    # ================== Commits ==================
    
    async def list_commits(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        limit: int = 10
    ) -> GitHubResult:
        """Lista commits"""
        return await self.execute("list_commits", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "limit": limit
        })
    
    # ================== Workflows / Actions ==================
    
    async def list_workflows(self, owner: str, repo: str) -> GitHubResult:
        """Lista workflows do repositório"""
        return await self.execute("list_workflows", {
            "owner": owner,
            "repo": repo
        })
    
    async def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main"
    ) -> GitHubResult:
        """Dispara workflow"""
        return await self.execute("trigger_workflow", {
            "owner": owner,
            "repo": repo,
            "workflow_id": workflow_id,
            "ref": ref
        })
    
    # ================== Utilitários ==================
    
    async def check_connection(self) -> bool:
        """Verifica conexão com GitHub Agent"""
        try:
            result = await self._request("GET", "/health")
            return "error" not in result
        except:
            return False
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Obtém status do GitHub Agent"""
        try:
            return await self._request("GET", "/status")
        except Exception as e:
            return {"error": str(e)}


class GitHubWorkflow:
    """
    Workflows comuns de GitHub para agentes especializados
    """
    
    def __init__(self, client: GitHubAgentClient):
        self.client = client
    
    async def create_project_repo(
        self,
        name: str,
        description: str,
        language: str,
        initial_files: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Cria repositório com estrutura inicial"""
        # Criar repo
        result = await self.client.create_repo(
            name=name,
            description=description,
            private=False,
            language=language
        )
        
        if not result.success:
            return {"success": False, "error": result.error}
        
        repo_data = result.data
        owner = repo_data.get("owner", {}).get("login", "")
        
        # Push arquivos iniciais se fornecidos
        if initial_files:
            push_result = await self.client.push_code(
                owner=owner,
                repo=name,
                files=initial_files,
                message="Initial commit from Specialized Agent"
            )
            
            if not push_result.success:
                return {
                    "success": True,
                    "repo": repo_data,
                    "warning": f"Repo criado mas push falhou: {push_result.error}"
                }
        
        return {"success": True, "repo": repo_data}
    
    async def submit_code_for_review(
        self,
        owner: str,
        repo: str,
        code: Dict[str, str],
        feature_name: str,
        description: str
    ) -> Dict[str, Any]:
        """Cria branch, commita código e abre PR"""
        branch_name = f"feature/{feature_name.lower().replace(' ', '-')}"
        
        # Criar branch
        branch_result = await self.client.create_branch(
            owner=owner,
            repo=repo,
            branch_name=branch_name
        )
        
        if not branch_result.success:
            return {"success": False, "error": f"Erro ao criar branch: {branch_result.error}"}
        
        # Push código
        push_result = await self.client.push_code(
            owner=owner,
            repo=repo,
            files=code,
            message=f"feat: {feature_name}",
            branch=branch_name
        )
        
        if not push_result.success:
            return {"success": False, "error": f"Erro no push: {push_result.error}"}
        
        # Criar PR
        pr_result = await self.client.create_pr(
            owner=owner,
            repo=repo,
            title=f"Feature: {feature_name}",
            body=description,
            head=branch_name,
            base="main"
        )
        
        if not pr_result.success:
            return {"success": False, "error": f"Erro ao criar PR: {pr_result.error}"}
        
        return {
            "success": True,
            "branch": branch_name,
            "pr": pr_result.data
        }
    
    async def fix_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        fix_code: Dict[str, str],
        fix_description: str
    ) -> Dict[str, Any]:
        """Cria PR para resolver issue"""
        branch_name = f"fix/issue-{issue_number}"
        
        # Criar branch
        await self.client.create_branch(
            owner=owner,
            repo=repo,
            branch_name=branch_name
        )
        
        # Push fix
        await self.client.push_code(
            owner=owner,
            repo=repo,
            files=fix_code,
            message=f"fix: resolve issue #{issue_number}",
            branch=branch_name
        )
        
        # Criar PR referenciando issue
        pr_result = await self.client.create_pr(
            owner=owner,
            repo=repo,
            title=f"Fix #{issue_number}",
            body=f"Closes #{issue_number}\n\n{fix_description}",
            head=branch_name,
            base="main"
        )
        
        return {
            "success": pr_result.success,
            "pr": pr_result.data if pr_result.success else None,
            "error": pr_result.error
        }


class DirectGitHubClient:
    """
    Cliente DIRETO para API do GitHub - não depende de agent externo.
    Usa a API REST do GitHub diretamente.
    """
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.api_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def check_connection(self) -> bool:
        """Verifica conexão com GitHub"""
        try:
            response = await self.client.get(
                f"{self.api_url}/user",
                headers=self.headers
            )
            return response.status_code == 200
        except:
            return False
    
    async def get_user(self) -> Dict:
        """Obtém usuário autenticado"""
        try:
            response = await self.client.get(
                f"{self.api_url}/user",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return {"error": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    async def list_repos(self, owner: str = None, per_page: int = 30) -> List[Dict]:
        """Lista repositórios"""
        try:
            if owner:
                url = f"{self.api_url}/users/{owner}/repos"
            else:
                url = f"{self.api_url}/user/repos"
            
            response = await self.client.get(
                url,
                headers=self.headers,
                params={"per_page": per_page, "sort": "updated"}
            )
            
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []
    
    async def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True
    ) -> Dict:
        """Cria novo repositório"""
        try:
            response = await self.client.post(
                f"{self.api_url}/user/repos",
                headers=self.headers,
                json={
                    "name": name,
                    "description": description,
                    "private": private,
                    "auto_init": auto_init
                }
            )
            
            if response.status_code == 201:
                repo = response.json()
                return {
                    "success": True,
                    "name": repo["name"],
                    "url": repo["html_url"],
                    "clone_url": repo["clone_url"],
                    "ssh_url": repo["ssh_url"]
                }
            elif response.status_code == 422:
                # Já existe - tentar obter info
                user = await self.get_user()
                if "login" in user:
                    return {
                        "success": True,
                        "name": name,
                        "url": f"https://github.com/{user['login']}/{name}",
                        "exists": True
                    }
            return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def push_project(
        self,
        project_path: str,
        repo_name: str,
        description: str = ""
    ) -> Dict:
        """Push projeto local para GitHub usando git CLI"""
        import subprocess
        from pathlib import Path
        
        # Criar repo
        repo_result = await self.create_repo(repo_name, description)
        if not repo_result.get("success"):
            return repo_result
        
        project = Path(project_path)
        if not project.exists():
            return {"success": False, "error": f"Projeto não encontrado: {project_path}"}
        
        # Obter usuário
        user = await self.get_user()
        username = user.get("login", "")
        
        # URL com token para autenticação
        clone_url = f"https://{self.token}@github.com/{username}/{repo_name}.git"
        
        try:
            # Comandos git
            cmds = [
                f"cd '{project_path}' && git init",
                f"cd '{project_path}' && git add -A",
                f"cd '{project_path}' && git commit -m 'Initial commit from Specialized Agent' --allow-empty",
                f"cd '{project_path}' && git branch -M main",
                f"cd '{project_path}' && git remote remove origin 2>/dev/null; git remote add origin {clone_url}",
                f"cd '{project_path}' && git push -u origin main --force"
            ]
            
            for cmd in cmds:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            
            return {
                "success": True,
                "name": repo_name,
                "url": f"https://github.com/{username}/{repo_name}",
                "message": "Projeto enviado com sucesso!"
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout no push"}
        except Exception as e:
            return {"success": False, "error": str(e)}
