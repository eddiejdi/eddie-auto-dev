#!/usr/bin/env python3
"""
GitHub MCP Server - Model Context Protocol Server para GitHub
Compatível com Continue, Cline, Roo Code, e outras extensões de IA
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Optional, List, Dict
from datetime import datetime

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        Resource,
        ResourceTemplate,
        Prompt,
        PromptMessage,
        PromptArgument,
    )
except ImportError:
    print("Instalando dependências MCP...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp", "httpx", "-q"])
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        Resource,
        ResourceTemplate,
        Prompt,
        PromptMessage,
        PromptArgument,
    )

import httpx

# Configuração de logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("github-mcp-server")

# =============================================================================
# CLIENTE GITHUB
# =============================================================================

class GitHubClient:
    """Cliente para API do GitHub"""
    
    def __init__(self, token: Optional[str] = None):
        # Prefer token from environment, otherwise try the vault (if available)
        env_token = os.getenv("GITHUB_TOKEN", "")
        if token:
            self.token = token
        elif env_token:
            self.token = env_token
        else:
            try:
                from tools.vault.secret_store import get_field
                self.token = get_field("shared/github_token", "password")
            except Exception:
                self.token = ""
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-MCP-Server/1.0"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
    
    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Faz requisição à API do GitHub"""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method, url, headers=self.headers, timeout=30.0, **kwargs
            )
            if response.status_code == 401:
                raise Exception("Token GitHub inválido ou expirado")
            if response.status_code == 403:
                raise Exception("Acesso negado. Verifique as permissões do token")
            if response.status_code == 404:
                raise Exception("Recurso não encontrado")
            response.raise_for_status()
            return response.json() if response.content else {}
    
    async def get_user(self) -> Dict[str, Any]:
        """Obtém informações do usuário autenticado"""
        return await self._request("GET", "/user")
    
    async def list_repos(self, visibility: str = "all", sort: str = "updated", 
                        per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista repositórios do usuário"""
        params = {"visibility": visibility, "sort": sort, "per_page": per_page}
        return await self._request("GET", "/user/repos", params=params)
    
    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Obtém detalhes de um repositório"""
        return await self._request("GET", f"/repos/{owner}/{repo}")
    
    async def create_repo(self, name: str, description: str = "", 
                         private: bool = False) -> Dict[str, Any]:
        """Cria um novo repositório"""
        data = {"name": name, "description": description, "private": private}
        return await self._request("POST", "/user/repos", json=data)
    
    async def delete_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Deleta um repositório"""
        return await self._request("DELETE", f"/repos/{owner}/{repo}")
    
    async def list_issues(self, owner: str, repo: str, state: str = "open",
                         per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista issues de um repositório"""
        params = {"state": state, "per_page": per_page}
        return await self._request("GET", f"/repos/{owner}/{repo}/issues", params=params)
    
    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Obtém detalhes de uma issue"""
        return await self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
    
    async def create_issue(self, owner: str, repo: str, title: str, 
                          body: str = "", labels: List[str] = None) -> Dict[str, Any]:
        """Cria uma nova issue"""
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        return await self._request("POST", f"/repos/{owner}/{repo}/issues", json=data)
    
    async def update_issue(self, owner: str, repo: str, issue_number: int,
                          title: str = None, body: str = None, 
                          state: str = None) -> Dict[str, Any]:
        """Atualiza uma issue"""
        data = {}
        if title:
            data["title"] = title
        if body:
            data["body"] = body
        if state:
            data["state"] = state
        return await self._request("PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", json=data)
    
    async def add_comment(self, owner: str, repo: str, issue_number: int,
                         body: str) -> Dict[str, Any]:
        """Adiciona comentário a uma issue/PR"""
        data = {"body": body}
        return await self._request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", json=data)
    
    async def list_prs(self, owner: str, repo: str, state: str = "open",
                      per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista pull requests de um repositório"""
        params = {"state": state, "per_page": per_page}
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls", params=params)
    
    async def get_pr(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Obtém detalhes de um pull request"""
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
    
    async def create_pr(self, owner: str, repo: str, title: str, head: str,
                       base: str = "main", body: str = "") -> Dict[str, Any]:
        """Cria um novo pull request"""
        data = {"title": title, "head": head, "base": base, "body": body}
        return await self._request("POST", f"/repos/{owner}/{repo}/pulls", json=data)
    
    async def merge_pr(self, owner: str, repo: str, pr_number: int,
                      merge_method: str = "merge") -> Dict[str, Any]:
        """Faz merge de um pull request"""
        data = {"merge_method": merge_method}
        return await self._request("PUT", f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", json=data)
    
    async def list_branches(self, owner: str, repo: str, 
                           per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista branches de um repositório"""
        params = {"per_page": per_page}
        return await self._request("GET", f"/repos/{owner}/{repo}/branches", params=params)
    
    async def get_branch(self, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        """Obtém detalhes de uma branch"""
        return await self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")
    
    async def list_commits(self, owner: str, repo: str, sha: str = None,
                          per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista commits de um repositório"""
        params = {"per_page": per_page}
        if sha:
            params["sha"] = sha
        return await self._request("GET", f"/repos/{owner}/{repo}/commits", params=params)
    
    async def get_commit(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Obtém detalhes de um commit"""
        return await self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}")
    
    async def search_code(self, query: str, per_page: int = 30) -> Dict[str, Any]:
        """Busca código no GitHub"""
        params = {"q": query, "per_page": per_page}
        return await self._request("GET", "/search/code", params=params)
    
    async def search_repos(self, query: str, sort: str = "stars",
                          per_page: int = 30) -> Dict[str, Any]:
        """Busca repositórios no GitHub"""
        params = {"q": query, "sort": sort, "per_page": per_page}
        return await self._request("GET", "/search/repositories", params=params)
    
    async def search_issues(self, query: str, sort: str = "created",
                           per_page: int = 30) -> Dict[str, Any]:
        """Busca issues no GitHub"""
        params = {"q": query, "sort": sort, "per_page": per_page}
        return await self._request("GET", "/search/issues", params=params)
    
    async def get_file_content(self, owner: str, repo: str, path: str,
                              ref: str = None) -> Dict[str, Any]:
        """Obtém conteúdo de um arquivo"""
        params = {}
        if ref:
            params["ref"] = ref
        return await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
    
    async def create_or_update_file(self, owner: str, repo: str, path: str,
                                   message: str, content: str, sha: str = None,
                                   branch: str = None) -> Dict[str, Any]:
        """Cria ou atualiza um arquivo"""
        import base64
        data = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode()
        }
        if sha:
            data["sha"] = sha
        if branch:
            data["branch"] = branch
        return await self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=data)
    
    async def list_workflows(self, owner: str, repo: str) -> Dict[str, Any]:
        """Lista workflows do GitHub Actions"""
        return await self._request("GET", f"/repos/{owner}/{repo}/actions/workflows")
    
    async def list_workflow_runs(self, owner: str, repo: str, 
                                per_page: int = 30) -> Dict[str, Any]:
        """Lista execuções de workflows"""
        params = {"per_page": per_page}
        return await self._request("GET", f"/repos/{owner}/{repo}/actions/runs", params=params)
    
    async def trigger_workflow(self, owner: str, repo: str, workflow_id: str,
                              ref: str = "main") -> Dict[str, Any]:
        """Dispara um workflow"""
        data = {"ref": ref}
        return await self._request("POST", f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches", json=data)
    
    async def list_releases(self, owner: str, repo: str,
                           per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista releases de um repositório"""
        params = {"per_page": per_page}
        return await self._request("GET", f"/repos/{owner}/{repo}/releases", params=params)
    
    async def create_release(self, owner: str, repo: str, tag_name: str,
                            name: str = "", body: str = "", 
                            draft: bool = False) -> Dict[str, Any]:
        """Cria uma nova release"""
        data = {"tag_name": tag_name, "name": name, "body": body, "draft": draft}
        return await self._request("POST", f"/repos/{owner}/{repo}/releases", json=data)
    
    async def list_gists(self, per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista gists do usuário"""
        params = {"per_page": per_page}
        return await self._request("GET", "/gists", params=params)
    
    async def create_gist(self, description: str, files: Dict[str, str],
                         public: bool = True) -> Dict[str, Any]:
        """Cria um novo gist"""
        gist_files = {name: {"content": content} for name, content in files.items()}
        data = {"description": description, "public": public, "files": gist_files}
        return await self._request("POST", "/gists", json=data)
    
    async def list_notifications(self, all_notifications: bool = False,
                                per_page: int = 30) -> List[Dict[str, Any]]:
        """Lista notificações"""
        params = {"all": all_notifications, "per_page": per_page}
        return await self._request("GET", "/notifications", params=params)
    
    async def get_rate_limit(self) -> Dict[str, Any]:
        """Obtém informações de rate limit"""
        return await self._request("GET", "/rate_limit")


# =============================================================================
# MCP SERVER
# =============================================================================

# Instância global do cliente GitHub
github_client = GitHubClient()

# Criar servidor MCP
server = Server("github-mcp-server")

# -----------------------------------------------------------------------------
# TOOLS (Ferramentas)
# -----------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> List[Tool]:
    """Lista todas as ferramentas disponíveis"""
    return [
        # Autenticação e Setup
        Tool(
            name="github_setup_guide",
            description="Guia interativo para configurar a conexão com o GitHub. Use esta ferramenta quando o token não estiver configurado ou quando o usuário precisar de ajuda para conectar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "step": {
                        "type": "string",
                        "enum": ["start", "create_token", "validate_token", "help"],
                        "default": "start",
                        "description": "Etapa do guia: start=início, create_token=instruções para criar token, validate_token=validar token existente, help=ajuda geral"
                    }
                }
            }
        ),
        Tool(
            name="github_connection_status",
            description="Verifica o status da conexão com o GitHub e fornece instruções se não estiver conectado.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="github_set_token",
            description="Define o token de autenticação do GitHub. Necessário antes de usar outras ferramentas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {
                        "type": "string",
                        "description": "Token de acesso pessoal do GitHub (PAT)"
                    }
                },
                "required": ["token"]
            }
        ),
        Tool(
            name="github_get_user",
            description="Obtém informações do usuário autenticado no GitHub",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # Repositórios
        Tool(
            name="github_list_repos",
            description="Lista repositórios do usuário autenticado",
            inputSchema={
                "type": "object",
                "properties": {
                    "visibility": {
                        "type": "string",
                        "enum": ["all", "public", "private"],
                        "default": "all",
                        "description": "Filtrar por visibilidade"
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["created", "updated", "pushed", "full_name"],
                        "default": "updated",
                        "description": "Ordenar por"
                    },
                    "per_page": {
                        "type": "integer",
                        "default": 30,
                        "description": "Número de resultados por página"
                    }
                }
            }
        ),
        Tool(
            name="github_get_repo",
            description="Obtém detalhes de um repositório específico",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Dono do repositório"},
                    "repo": {"type": "string", "description": "Nome do repositório"}
                },
                "required": ["owner", "repo"]
            }
        ),
        Tool(
            name="github_create_repo",
            description="Cria um novo repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do repositório"},
                    "description": {"type": "string", "description": "Descrição"},
                    "private": {"type": "boolean", "default": False, "description": "Se é privado"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="github_delete_repo",
            description="Deleta um repositório (CUIDADO: irreversível!)",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Dono do repositório"},
                    "repo": {"type": "string", "description": "Nome do repositório"}
                },
                "required": ["owner", "repo"]
            }
        ),
        
        # Issues
        Tool(
            name="github_list_issues",
            description="Lista issues de um repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Dono do repositório"},
                    "repo": {"type": "string", "description": "Nome do repositório"},
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "default": "open"
                    },
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["owner", "repo"]
            }
        ),
        Tool(
            name="github_get_issue",
            description="Obtém detalhes de uma issue específica",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "issue_number": {"type": "integer", "description": "Número da issue"}
                },
                "required": ["owner", "repo", "issue_number"]
            }
        ),
        Tool(
            name="github_create_issue",
            description="Cria uma nova issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "title": {"type": "string", "description": "Título da issue"},
                    "body": {"type": "string", "description": "Corpo/descrição da issue"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels para adicionar"
                    }
                },
                "required": ["owner", "repo", "title"]
            }
        ),
        Tool(
            name="github_update_issue",
            description="Atualiza uma issue existente",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "issue_number": {"type": "integer"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "state": {"type": "string", "enum": ["open", "closed"]}
                },
                "required": ["owner", "repo", "issue_number"]
            }
        ),
        Tool(
            name="github_add_comment",
            description="Adiciona um comentário a uma issue ou PR",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "issue_number": {"type": "integer"},
                    "body": {"type": "string", "description": "Texto do comentário"}
                },
                "required": ["owner", "repo", "issue_number", "body"]
            }
        ),
        
        # Pull Requests
        Tool(
            name="github_list_prs",
            description="Lista pull requests de um repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "default": "open"
                    },
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["owner", "repo"]
            }
        ),
        Tool(
            name="github_get_pr",
            description="Obtém detalhes de um pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "pr_number": {"type": "integer"}
                },
                "required": ["owner", "repo", "pr_number"]
            }
        ),
        Tool(
            name="github_create_pr",
            description="Cria um novo pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                    "head": {"type": "string", "description": "Branch de origem"},
                    "base": {"type": "string", "default": "main", "description": "Branch de destino"},
                    "body": {"type": "string"}
                },
                "required": ["owner", "repo", "title", "head"]
            }
        ),
        Tool(
            name="github_merge_pr",
            description="Faz merge de um pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "pr_number": {"type": "integer"},
                    "merge_method": {
                        "type": "string",
                        "enum": ["merge", "squash", "rebase"],
                        "default": "merge"
                    }
                },
                "required": ["owner", "repo", "pr_number"]
            }
        ),
        
        # Branches
        Tool(
            name="github_list_branches",
            description="Lista branches de um repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["owner", "repo"]
            }
        ),
        
        # Commits
        Tool(
            name="github_list_commits",
            description="Lista commits de um repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "sha": {"type": "string", "description": "Branch ou SHA para filtrar"},
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["owner", "repo"]
            }
        ),
        Tool(
            name="github_get_commit",
            description="Obtém detalhes de um commit",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "sha": {"type": "string", "description": "SHA do commit"}
                },
                "required": ["owner", "repo", "sha"]
            }
        ),
        
        # Busca
        Tool(
            name="github_search_code",
            description="Busca código no GitHub",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query de busca"},
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="github_search_repos",
            description="Busca repositórios no GitHub",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "sort": {
                        "type": "string",
                        "enum": ["stars", "forks", "updated"],
                        "default": "stars"
                    },
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="github_search_issues",
            description="Busca issues e PRs no GitHub",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "sort": {
                        "type": "string",
                        "enum": ["created", "updated", "comments"],
                        "default": "created"
                    },
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["query"]
            }
        ),
        
        # Arquivos
        Tool(
            name="github_get_file",
            description="Obtém conteúdo de um arquivo do repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "path": {"type": "string", "description": "Caminho do arquivo"},
                    "ref": {"type": "string", "description": "Branch ou commit"}
                },
                "required": ["owner", "repo", "path"]
            }
        ),
        Tool(
            name="github_create_or_update_file",
            description="Cria ou atualiza um arquivo no repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "path": {"type": "string"},
                    "message": {"type": "string", "description": "Mensagem de commit"},
                    "content": {"type": "string", "description": "Conteúdo do arquivo"},
                    "sha": {"type": "string", "description": "SHA do arquivo (para update)"},
                    "branch": {"type": "string"}
                },
                "required": ["owner", "repo", "path", "message", "content"]
            }
        ),
        
        # GitHub Actions
        Tool(
            name="github_list_workflows",
            description="Lista workflows do GitHub Actions",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"}
                },
                "required": ["owner", "repo"]
            }
        ),
        Tool(
            name="github_list_workflow_runs",
            description="Lista execuções de workflows",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["owner", "repo"]
            }
        ),
        Tool(
            name="github_trigger_workflow",
            description="Dispara um workflow manualmente",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "workflow_id": {"type": "string"},
                    "ref": {"type": "string", "default": "main"}
                },
                "required": ["owner", "repo", "workflow_id"]
            }
        ),
        
        # Releases
        Tool(
            name="github_list_releases",
            description="Lista releases de um repositório",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "per_page": {"type": "integer", "default": 30}
                },
                "required": ["owner", "repo"]
            }
        ),
        Tool(
            name="github_create_release",
            description="Cria uma nova release",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "tag_name": {"type": "string"},
                    "name": {"type": "string"},
                    "body": {"type": "string"},
                    "draft": {"type": "boolean", "default": False}
                },
                "required": ["owner", "repo", "tag_name"]
            }
        ),
        
        # Gists
        Tool(
            name="github_list_gists",
            description="Lista gists do usuário",
            inputSchema={
                "type": "object",
                "properties": {
                    "per_page": {"type": "integer", "default": 30}
                }
            }
        ),
        Tool(
            name="github_create_gist",
            description="Cria um novo gist",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "files": {
                        "type": "object",
                        "description": "Objeto com nome do arquivo como chave e conteúdo como valor"
                    },
                    "public": {"type": "boolean", "default": True}
                },
                "required": ["description", "files"]
            }
        ),
        
        # Outros
        Tool(
            name="github_list_notifications",
            description="Lista notificações do usuário",
            inputSchema={
                "type": "object",
                "properties": {
                    "all": {"type": "boolean", "default": False},
                    "per_page": {"type": "integer", "default": 30}
                }
            }
        ),
        Tool(
            name="github_rate_limit",
            description="Verifica o rate limit da API",
            inputSchema={"type": "object", "properties": {}}
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Executa uma ferramenta"""
    global github_client
    
    # URL para criar token com scopes pré-selecionados
    TOKEN_CREATION_URL = "https://github.com/settings/tokens/new?scopes=repo,read:user,read:org,gist,notifications,workflow&description=MCP%20GitHub%20Server"
    
    # Mensagem de ajuda para conexão
    CONNECTION_HELP = f"""
🔐 **Conexão com GitHub não configurada!**

Para usar as funcionalidades do GitHub, você precisa criar um Token de Acesso Pessoal (PAT).

## 📋 Passo a Passo:

### 1️⃣ Criar o Token
👉 **Clique aqui para criar seu token:** 
{TOKEN_CREATION_URL}

### 2️⃣ Na página do GitHub:
- O nome "MCP GitHub Server" já estará preenchido
- Os scopes necessários já estarão selecionados:
  - ✅ `repo` - Acesso a repositórios
  - ✅ `read:user` - Ler perfil
  - ✅ `read:org` - Ler organizações
  - ✅ `gist` - Gerenciar gists
  - ✅ `notifications` - Notificações
  - ✅ `workflow` - GitHub Actions

### 3️⃣ Definir expiração
- Escolha "No expiration" para não expirar
- Ou defina uma data de expiração

### 4️⃣ Gerar e copiar
- Clique em **"Generate token"**
- **IMPORTANTE:** Copie o token (começa com `ghp_`)
- ⚠️ Você só verá o token uma vez!

### 5️⃣ Configurar o token
Depois de copiar, me envie o token que eu configuro para você!

Ou use o comando:
github_set_token com seu token
---
💡 **Dica:** Guarde o token em um lugar seguro caso precise usar novamente.
"""
    
    try:
        # Guia de Setup
        if name == "github_setup_guide":
            step = arguments.get("step", "start")
            
            if step == "start":
                return [TextContent(type="text", text=CONNECTION_HELP)]
            
            elif step == "create_token":
                return [TextContent(
                    type="text",
                    text=f"""
## 🔑 Criar Token do GitHub

### Link Direto (recomendado):
👉 {TOKEN_CREATION_URL}

Este link já pré-seleciona todos os scopes necessários!

### Ou manualmente:
1. Acesse: https://github.com/settings/tokens
2. Clique em "Generate new token (classic)"
3. Selecione os scopes:
   - `repo` - Repositórios
   - `read:user` - Perfil
   - `read:org` - Organizações
   - `gist` - Gists
   - `notifications` - Notificações
   - `workflow` - Actions

Após criar, me envie o token que começa com `ghp_`
"""
                )]
            
            elif step == "validate_token":
                if github_client.is_authenticated:
                    try:
                        user = await github_client.get_user()
                        return [TextContent(
                            type="text",
                            text=f"""
✅ **Token válido!**

Conectado como: **{user['login']}**
Nome: {user.get('name', 'N/A')}
Email: {user.get('email', 'N/A')}
Repos públicos: {user['public_repos']}
Followers: {user['followers']}

Você já pode usar todos os comandos do GitHub!
"""
                        )]
                    except Exception as e:
                        return [TextContent(
                            type="text",
                            text=f"❌ Token inválido ou expirado: {str(e)}\n\n{CONNECTION_HELP}"
                        )]
                else:
                    return [TextContent(type="text", text=CONNECTION_HELP)]
            
            elif step == "help":
                return [TextContent(
                    type="text",
                    text=f"""
## ❓ Ajuda - GitHub MCP Server

### Comandos Disponíveis:
- `github_setup_guide` - Este guia de configuração
- `github_connection_status` - Verificar status da conexão
- `github_set_token` - Configurar seu token

### Após conectar, você pode:
- Listar e criar repositórios
- Gerenciar issues e PRs
- Buscar código no GitHub
- Gerenciar releases e gists
- E muito mais!

### Link para criar token:
{TOKEN_CREATION_URL}

### Problemas comuns:
1. **Token expirado** - Crie um novo token
2. **Permissão negada** - Verifique os scopes do token
3. **Rate limit** - Aguarde alguns minutos
"""
                )]
        
        # Status da conexão
        if name == "github_connection_status":
            if github_client.is_authenticated:
                try:
                    user = await github_client.get_user()
                    rate = await github_client.get_rate_limit()
                    rate_info = rate.get("rate", {})
                    return [TextContent(
                        type="text",
                        text=f"""
✅ **Conectado ao GitHub!**

👤 **Usuário:** {user['login']}
📛 **Nome:** {user.get('name', 'N/A')}
📧 **Email:** {user.get('email', 'Privado')}
📂 **Repos públicos:** {user['public_repos']}
👥 **Followers:** {user['followers']} | Following: {user['following']}

📊 **Rate Limit:**
- Restante: {rate_info.get('remaining', 'N/A')} / {rate_info.get('limit', 'N/A')}
- Reset: {datetime.fromtimestamp(rate_info.get('reset', 0)).strftime('%H:%M:%S')}

✨ Tudo pronto! Você pode usar todos os comandos do GitHub.
"""
                    )]
                except Exception as e:
                    return [TextContent(
                        type="text",
                        text=f"⚠️ Token configurado mas houve erro: {str(e)}\n\nTente criar um novo token:\n{TOKEN_CREATION_URL}"
                    )]
            else:
                return [TextContent(type="text", text=CONNECTION_HELP)]
        
        # Autenticação
        if name == "github_set_token":
            token = arguments.get("token", "").strip()
            
            if not token:
                return [TextContent(
                    type="text",
                    text=f"❌ Token não fornecido!\n\n{CONNECTION_HELP}"
                )]
            
            # Limpar possíveis caracteres extras
            if token.startswith('"') or token.startswith("'"):
                token = token[1:]
            if token.endswith('"') or token.endswith("'"):
                token = token[:-1]
            
            github_client = GitHubClient(token)
            
            try:
                user = await github_client.get_user()
                return [TextContent(
                    type="text",
                    text=f"""
✅ **Autenticado com sucesso!**

👤 **Usuário:** {user['login']}
📛 **Nome:** {user.get('name', 'N/A')}
📂 **Repos públicos:** {user['public_repos']}
🔗 **Perfil:** {user['html_url']}

🎉 Agora você pode usar todos os comandos do GitHub!

**Exemplos de comandos:**
- "Liste meus repositórios"
- "Crie uma issue no repo X"
- "Busque código com função Y"
- "Mostre os PRs abertos"
"""
                )]
            except Exception as e:
                github_client = GitHubClient()  # Reset
                return [TextContent(
                    type="text",
                    text=f"""
❌ **Token inválido!**

Erro: {str(e)}

O token pode estar:
- Expirado
- Com formato incorreto
- Sem as permissões necessárias

👉 **Crie um novo token aqui:**
{TOKEN_CREATION_URL}
"""
                )]
        
        # Verificar autenticação para outras ferramentas
        if not github_client.is_authenticated and name != "github_rate_limit":
            return [TextContent(type="text", text=CONNECTION_HELP)]
        
        # Usuário
        if name == "github_get_user":
            result = await github_client.get_user()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        # Repositórios
        elif name == "github_list_repos":
            result = await github_client.list_repos(
                visibility=arguments.get("visibility", "all"),
                sort=arguments.get("sort", "updated"),
                per_page=arguments.get("per_page", 30)
            )
            repos_summary = "\n".join([
                f"• {r['full_name']} {'🔒' if r['private'] else '🌐'} ⭐{r['stargazers_count']}"
                for r in result[:20]
            ])
            return [TextContent(type="text", text=f"Repositórios ({len(result)}):\n{repos_summary}")]
        
        elif name == "github_get_repo":
            result = await github_client.get_repo(arguments["owner"], arguments["repo"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "github_create_repo":
            result = await github_client.create_repo(
                name=arguments["name"],
                description=arguments.get("description", ""),
                private=arguments.get("private", False)
            )
            return [TextContent(
                type="text",
                text=f"✅ Repositório criado: {result['html_url']}"
            )]
        
        elif name == "github_delete_repo":
            await github_client.delete_repo(arguments["owner"], arguments["repo"])
            return [TextContent(type="text", text=f"✅ Repositório {arguments['owner']}/{arguments['repo']} deletado")]
        
        # Issues
        elif name == "github_list_issues":
            result = await github_client.list_issues(
                owner=arguments["owner"],
                repo=arguments["repo"],
                state=arguments.get("state", "open"),
                per_page=arguments.get("per_page", 30)
            )
            issues_summary = "\n".join([
                f"#{i['number']} {i['title']} [{i['state']}]"
                for i in result[:20]
            ])
            return [TextContent(type="text", text=f"Issues ({len(result)}):\n{issues_summary}")]
        
        elif name == "github_get_issue":
            result = await github_client.get_issue(
                arguments["owner"], arguments["repo"], arguments["issue_number"]
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "github_create_issue":
            result = await github_client.create_issue(
                owner=arguments["owner"],
                repo=arguments["repo"],
                title=arguments["title"],
                body=arguments.get("body", ""),
                labels=arguments.get("labels")
            )
            return [TextContent(
                type="text",
                text=f"✅ Issue criada: #{result['number']} - {result['html_url']}"
            )]
        
        elif name == "github_update_issue":
            result = await github_client.update_issue(
                owner=arguments["owner"],
                repo=arguments["repo"],
                issue_number=arguments["issue_number"],
                title=arguments.get("title"),
                body=arguments.get("body"),
                state=arguments.get("state")
            )
            return [TextContent(type="text", text=f"✅ Issue #{arguments['issue_number']} atualizada")]
        
        elif name == "github_add_comment":
            result = await github_client.add_comment(
                owner=arguments["owner"],
                repo=arguments["repo"],
                issue_number=arguments["issue_number"],
                body=arguments["body"]
            )
            return [TextContent(type="text", text=f"✅ Comentário adicionado: {result['html_url']}")]
        
        # Pull Requests
        elif name == "github_list_prs":
            result = await github_client.list_prs(
                owner=arguments["owner"],
                repo=arguments["repo"],
                state=arguments.get("state", "open"),
                per_page=arguments.get("per_page", 30)
            )
            prs_summary = "\n".join([
                f"#{p['number']} {p['title']} [{p['state']}] {p['head']['ref']} → {p['base']['ref']}"
                for p in result[:20]
            ])
            return [TextContent(type="text", text=f"Pull Requests ({len(result)}):\n{prs_summary}")]
        
        elif name == "github_get_pr":
            result = await github_client.get_pr(
                arguments["owner"], arguments["repo"], arguments["pr_number"]
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "github_create_pr":
            result = await github_client.create_pr(
                owner=arguments["owner"],
                repo=arguments["repo"],
                title=arguments["title"],
                head=arguments["head"],
                base=arguments.get("base", "main"),
                body=arguments.get("body", "")
            )
            return [TextContent(
                type="text",
                text=f"✅ PR criado: #{result['number']} - {result['html_url']}"
            )]
        
        elif name == "github_merge_pr":
            result = await github_client.merge_pr(
                owner=arguments["owner"],
                repo=arguments["repo"],
                pr_number=arguments["pr_number"],
                merge_method=arguments.get("merge_method", "merge")
            )
            return [TextContent(type="text", text=f"✅ PR #{arguments['pr_number']} merged!")]
        
        # Branches
        elif name == "github_list_branches":
            result = await github_client.list_branches(
                owner=arguments["owner"],
                repo=arguments["repo"],
                per_page=arguments.get("per_page", 30)
            )
            branches = "\n".join([f"• {b['name']}" for b in result])
            return [TextContent(type="text", text=f"Branches:\n{branches}")]
        
        # Commits
        elif name == "github_list_commits":
            result = await github_client.list_commits(
                owner=arguments["owner"],
                repo=arguments["repo"],
                sha=arguments.get("sha"),
                per_page=arguments.get("per_page", 30)
            )
            commits = "\n".join([
                f"• {c['sha'][:7]} - {c['commit']['message'].split(chr(10))[0]}"
                for c in result[:20]
            ])
            return [TextContent(type="text", text=f"Commits:\n{commits}")]
        
        elif name == "github_get_commit":
            result = await github_client.get_commit(
                arguments["owner"], arguments["repo"], arguments["sha"]
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        # Busca
        elif name == "github_search_code":
            result = await github_client.search_code(
                query=arguments["query"],
                per_page=arguments.get("per_page", 30)
            )
            items = result.get("items", [])
            search_results = "\n".join([
                f"• {i['repository']['full_name']}/{i['path']}"
                for i in items[:20]
            ])
            return [TextContent(
                type="text",
                text=f"Resultados ({result['total_count']}):\n{search_results}"
            )]
        
        elif name == "github_search_repos":
            result = await github_client.search_repos(
                query=arguments["query"],
                sort=arguments.get("sort", "stars"),
                per_page=arguments.get("per_page", 30)
            )
            items = result.get("items", [])
            search_results = "\n".join([
                f"• {r['full_name']} ⭐{r['stargazers_count']} - {r.get('description', '')[:50]}"
                for r in items[:20]
            ])
            return [TextContent(
                type="text",
                text=f"Repositórios ({result['total_count']}):\n{search_results}"
            )]
        
        elif name == "github_search_issues":
            result = await github_client.search_issues(
                query=arguments["query"],
                sort=arguments.get("sort", "created"),
                per_page=arguments.get("per_page", 30)
            )
            items = result.get("items", [])
            search_results = "\n".join([
                f"• {i['repository_url'].split('/')[-2]}/{i['repository_url'].split('/')[-1]}#{i['number']} {i['title']}"
                for i in items[:20]
            ])
            return [TextContent(
                type="text",
                text=f"Issues/PRs ({result['total_count']}):\n{search_results}"
            )]
        
        # Arquivos
        elif name == "github_get_file":
            result = await github_client.get_file_content(
                owner=arguments["owner"],
                repo=arguments["repo"],
                path=arguments["path"],
                ref=arguments.get("ref")
            )
            import base64
            content = base64.b64decode(result.get("content", "")).decode("utf-8")
            return [TextContent(
                type="text",
                text=f"Arquivo: {result['path']}\n\n```\n{content}\n```"
            )]
        
        elif name == "github_create_or_update_file":
            result = await github_client.create_or_update_file(
                owner=arguments["owner"],
                repo=arguments["repo"],
                path=arguments["path"],
                message=arguments["message"],
                content=arguments["content"],
                sha=arguments.get("sha"),
                branch=arguments.get("branch")
            )
            return [TextContent(
                type="text",
                text=f"✅ Arquivo salvo: {result['content']['html_url']}"
            )]
        
        # GitHub Actions
        elif name == "github_list_workflows":
            result = await github_client.list_workflows(
                arguments["owner"], arguments["repo"]
            )
            workflows = result.get("workflows", [])
            wf_list = "\n".join([
                f"• {w['name']} (ID: {w['id']}) - {w['state']}"
                for w in workflows
            ])
            return [TextContent(type="text", text=f"Workflows:\n{wf_list}")]
        
        elif name == "github_list_workflow_runs":
            result = await github_client.list_workflow_runs(
                owner=arguments["owner"],
                repo=arguments["repo"],
                per_page=arguments.get("per_page", 30)
            )
            runs = result.get("workflow_runs", [])
            runs_list = "\n".join([
                f"• {r['name']} - {r['status']} ({r['conclusion'] or 'running'})"
                for r in runs[:20]
            ])
            return [TextContent(type="text", text=f"Workflow Runs:\n{runs_list}")]
        
        elif name == "github_trigger_workflow":
            await github_client.trigger_workflow(
                owner=arguments["owner"],
                repo=arguments["repo"],
                workflow_id=arguments["workflow_id"],
                ref=arguments.get("ref", "main")
            )
            return [TextContent(type="text", text=f"✅ Workflow disparado!")]
        
        # Releases
        elif name == "github_list_releases":
            result = await github_client.list_releases(
                owner=arguments["owner"],
                repo=arguments["repo"],
                per_page=arguments.get("per_page", 30)
            )
            releases = "\n".join([
                f"• {r['tag_name']} - {r['name']} ({r['published_at'][:10]})"
                for r in result[:20]
            ])
            return [TextContent(type="text", text=f"Releases:\n{releases}")]
        
        elif name == "github_create_release":
            result = await github_client.create_release(
                owner=arguments["owner"],
                repo=arguments["repo"],
                tag_name=arguments["tag_name"],
                name=arguments.get("name", ""),
                body=arguments.get("body", ""),
                draft=arguments.get("draft", False)
            )
            return [TextContent(
                type="text",
                text=f"✅ Release criada: {result['html_url']}"
            )]
        
        # Gists
        elif name == "github_list_gists":
            result = await github_client.list_gists(
                per_page=arguments.get("per_page", 30)
            )
            gists = "\n".join([
                f"• {g['id']} - {g.get('description', 'Sem descrição')[:50]}"
                for g in result[:20]
            ])
            return [TextContent(type="text", text=f"Gists:\n{gists}")]
        
        elif name == "github_create_gist":
            result = await github_client.create_gist(
                description=arguments["description"],
                files=arguments["files"],
                public=arguments.get("public", True)
            )
            return [TextContent(
                type="text",
                text=f"✅ Gist criado: {result['html_url']}"
            )]
        
        # Outros
        elif name == "github_list_notifications":
            result = await github_client.list_notifications(
                all_notifications=arguments.get("all", False),
                per_page=arguments.get("per_page", 30)
            )
            if not result:
                return [TextContent(type="text", text="Nenhuma notificação")]
            notifs = "\n".join([
                f"• [{n['reason']}] {n['subject']['title']}"
                for n in result[:20]
            ])
            return [TextContent(type="text", text=f"Notificações:\n{notifs}")]
        
        elif name == "github_rate_limit":
            result = await github_client.get_rate_limit()
            rate = result.get("rate", {})
            return [TextContent(
                type="text",
                text=f"Rate Limit:\n"
                     f"• Limite: {rate.get('limit', 'N/A')}\n"
                     f"• Restante: {rate.get('remaining', 'N/A')}\n"
                     f"• Reset: {datetime.fromtimestamp(rate.get('reset', 0)).strftime('%H:%M:%S')}"
            )]
        
        else:
            return [TextContent(type="text", text=f"❌ Ferramenta desconhecida: {name}")]
    
    except Exception as e:
        logger.error(f"Erro ao executar {name}: {e}")
        return [TextContent(type="text", text=f"❌ Erro: {str(e)}")]


# -----------------------------------------------------------------------------
# RESOURCES (Recursos)
# -----------------------------------------------------------------------------

@server.list_resources()
async def list_resources() -> List[Resource]:
    """Lista recursos disponíveis"""
    if not github_client.is_authenticated:
        return []
    
    try:
        user = await github_client.get_user()
        repos = await github_client.list_repos(per_page=10)
        
        resources = [
            Resource(
                uri=f"github://user/{user['login']}",
                name=f"Usuário: {user['login']}",
                description=f"Perfil do usuário {user['login']}",
                mimeType="application/json"
            )
        ]
        
        for repo in repos:
            resources.append(Resource(
                uri=f"github://repo/{repo['full_name']}",
                name=repo['full_name'],
                description=repo.get('description', 'Sem descrição'),
                mimeType="application/json"
            ))
        
        return resources
    except:
        return []


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Lê um recurso"""
    if uri.startswith("github://user/"):
        username = uri.split("/")[-1]
        user = await github_client.get_user()
        return json.dumps(user, indent=2)
    
    elif uri.startswith("github://repo/"):
        parts = uri.replace("github://repo/", "").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            result = await github_client.get_repo(owner, repo)
            return json.dumps(result, indent=2)
    
    return json.dumps({"error": "Recurso não encontrado"})


# -----------------------------------------------------------------------------
# PROMPTS
# -----------------------------------------------------------------------------

@server.list_prompts()
async def list_prompts() -> List[Prompt]:
    """Lista prompts disponíveis"""
    return [
        Prompt(
            name="github-setup",
            description="Configurar token do GitHub",
            arguments=[
                PromptArgument(
                    name="token",
                    description="Seu token de acesso pessoal do GitHub",
                    required=True
                )
            ]
        ),
        Prompt(
            name="list-my-repos",
            description="Listar meus repositórios",
            arguments=[]
        ),
        Prompt(
            name="create-issue",
            description="Criar uma nova issue",
            arguments=[
                PromptArgument(name="repo", description="Repositório (owner/repo)", required=True),
                PromptArgument(name="title", description="Título da issue", required=True),
                PromptArgument(name="body", description="Descrição da issue", required=False)
            ]
        ),
        Prompt(
            name="search-code",
            description="Buscar código no GitHub",
            arguments=[
                PromptArgument(name="query", description="O que buscar", required=True)
            ]
        )
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: Dict[str, str]) -> List[PromptMessage]:
    """Retorna um prompt"""
    if name == "github-setup":
        return [PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"Configure o token GitHub: {arguments.get('token', '[TOKEN]')}"
            )
        )]
    
    elif name == "list-my-repos":
        return [PromptMessage(
            role="user",
            content=TextContent(type="text", text="Liste meus repositórios do GitHub")
        )]
    
    elif name == "create-issue":
        return [PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"Crie uma issue no repositório {arguments.get('repo')} "
                     f"com título '{arguments.get('title')}' "
                     f"e descrição: {arguments.get('body', 'Sem descrição')}"
            )
        )]
    
    elif name == "search-code":
        return [PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"Busque código no GitHub: {arguments.get('query')}"
            )
        )]
    
    return []


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Inicia o servidor MCP"""
    logger.info("🚀 Iniciando GitHub MCP Server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

