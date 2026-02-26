#!/usr/bin/env python3
"""
MCP Helper para PyCharm
Facilita a chamada de MCP servers remotos do homelab diretamente do Python Console
"""

import subprocess
import json
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configurações
HOMELAB_HOST = "homelab@192.168.15.2"
HOMELAB_BASE = "/home/homelab/eddie-auto-dev"

MCP_SERVERS = {
    "github": f"{HOMELAB_BASE}/github-mcp-server/src/github_mcp_server.py",
    "ssh": f"{HOMELAB_BASE}/ssh_agent_mcp.py",
    "rag": f"{HOMELAB_BASE}/rag-mcp-server/src/rag_mcp_server.py",
    "homelab": "/home/homelab/estou-aqui-deploy/scripts/homelab_mcp_server.py",
}


class MCPClient:
    """Cliente para invocar MCP servers remotos via SSH"""

    def __init__(self, server_name: str):
        """
        Inicializa cliente MCP

        Args:
            server_name: Nome do servidor ('github', 'ssh', 'rag', 'homelab')
        """
        if server_name not in MCP_SERVERS:
            raise ValueError(f"Servidor '{server_name}' não encontrado. Disponíveis: {list(MCP_SERVERS.keys())}")

        self.server_name = server_name
        self.server_path = MCP_SERVERS[server_name]

    def execute(self, tool_name: str, params: Dict[str, Any] = None, timeout: int = 30) -> Dict[str, Any]:
        """
        Executa uma ferramenta no MCP server

        Args:
            tool_name: Nome da ferramenta (ex: 'github_list_repos')
            params: Parâmetros da ferramenta
            timeout: Timeout em segundos

        Returns:
            Resultado da execução
        """
        if params is None:
            params = {}

        # Criar payload JSON
        payload = json.dumps({
            "tool": tool_name,
            "params": params
        })

        # Comando SSH
        cmd = [
            "ssh", HOMELAB_HOST,
            f"python3 {self.server_path} --tool {tool_name} --params '{payload}'"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                # Tentar parsear JSON
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"success": True, "output": result.stdout}
            else:
                return {
                    "success": False,
                    "error": result.stderr or result.stdout
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_tools(self) -> List[str]:
        """Lista ferramentas disponíveis no servidor"""
        cmd = [
            "ssh", HOMELAB_HOST,
            f"python3 {self.server_path} --list-tools"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except:
                    # Fallback: extrair do output
                    return result.stdout.strip().split("\n")
            return []
        except:
            return []


# ============================================================================
# Funções de conveniência para cada servidor MCP
# ============================================================================

class GitHubMCP(MCPClient):
    """Cliente para GitHub MCP Server"""

    def __init__(self):
        super().__init__("github")

    def list_repos(self, owner: Optional[str] = None) -> Dict[str, Any]:
        """Lista repositórios"""
        params = {"owner": owner} if owner else {}
        return self.execute("github_list_repos", params)

    def create_issue(self, repo: str, title: str, body: str, owner: Optional[str] = None) -> Dict[str, Any]:
        """Cria uma issue"""
        return self.execute("github_create_issue", {
            "repo": repo,
            "title": title,
            "body": body,
            "owner": owner
        })

    def search_code(self, query: str, repo: Optional[str] = None) -> Dict[str, Any]:
        """Busca código"""
        params = {"query": query}
        if repo:
            params["repo"] = repo
        return self.execute("github_search_code", params)

    def list_prs(self, repo: str, owner: Optional[str] = None, state: str = "open") -> Dict[str, Any]:
        """Lista Pull Requests"""
        return self.execute("github_list_prs", {
            "repo": repo,
            "owner": owner,
            "state": state
        })


class SSHAgentMCP(MCPClient):
    """Cliente para SSH Agent MCP"""

    def __init__(self):
        super().__init__("ssh")

    def list_hosts(self) -> Dict[str, Any]:
        """Lista hosts SSH configurados"""
        return self.execute("ssh_list_hosts")

    def execute_command(self, host: str, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Executa comando em host remoto"""
        return self.execute("ssh_execute", {
            "host": host,
            "command": command,
            "timeout": timeout
        })

    def get_system_info(self, host: str) -> Dict[str, Any]:
        """Obtém informações do sistema"""
        return self.execute("ssh_get_system_info", {"host": host})


class RAGMCP(MCPClient):
    """Cliente para RAG MCP Server"""

    def __init__(self):
        super().__init__("rag")

    def search(self, query: str, collection: str = "default", limit: int = 5) -> Dict[str, Any]:
        """Busca semântica em documentos"""
        return self.execute("rag_search", {
            "query": query,
            "collection": collection,
            "limit": limit
        })

    def index_document(self, content: str, collection: str = "default", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Indexa novo documento"""
        return self.execute("rag_index", {
            "content": content,
            "collection": collection,
            "metadata": metadata or {}
        })

    def list_collections(self) -> Dict[str, Any]:
        """Lista coleções disponíveis"""
        return self.execute("rag_list_collections")


class HomelabMCP(MCPClient):
    """Cliente para Homelab MCP Server"""

    def __init__(self):
        super().__init__("homelab")

    def docker_ps(self) -> Dict[str, Any]:
        """Lista containers Docker"""
        return self.execute("homelab_docker_ps")

    def systemctl_status(self, service: str) -> Dict[str, Any]:
        """Verifica status de serviço systemd"""
        return self.execute("homelab_systemctl_status", {"service": service})

    def system_metrics(self) -> Dict[str, Any]:
        """Obtém métricas do sistema"""
        return self.execute("homelab_system_metrics")


# ============================================================================
# Funções de conveniência para uso rápido
# ============================================================================

def quick_ssh(command: str, host: str = "homelab") -> str:
    """
    Executa comando SSH rapidamente

    Args:
        command: Comando a executar
        host: Host SSH (padrão: 'homelab')

    Returns:
        Output do comando
    """
    ssh = SSHAgentMCP()
    result = ssh.execute_command(host, command)

    if result.get("success"):
        return result.get("output", "")
    else:
        return f"ERROR: {result.get('error')}"


def quick_github_search(query: str, repo: Optional[str] = None) -> List[Dict]:
    """
    Busca rápida no GitHub

    Args:
        query: Termo de busca
        repo: Repositório (opcional)

    Returns:
        Lista de resultados
    """
    github = GitHubMCP()
    result = github.search_code(query, repo)

    if result.get("success"):
        return result.get("results", [])
    else:
        print(f"Erro: {result.get('error')}")
        return []


def quick_rag_search(query: str, collection: str = "homelab") -> List[Dict]:
    """
    Busca rápida no RAG

    Args:
        query: Pergunta/termo de busca
        collection: Coleção (padrão: 'homelab')

    Returns:
        Resultados da busca
    """
    rag = RAGMCP()
    result = rag.search(query, collection)

    if result.get("success"):
        return result.get("results", [])
    else:
        print(f"Erro: {result.get('error')}")
        return []


# ============================================================================
# Exemplos de uso
# ============================================================================

def examples():
    """Mostra exemplos de uso"""
    print("=" * 70)
    print("EXEMPLOS DE USO - MCP Helper")
    print("=" * 70)

    print("""
# 1. GitHub MCP - Listar repositórios
github = GitHubMCP()
repos = github.list_repos(owner="eddiejdi")
print(repos)

# 2. SSH Agent - Executar comando remoto
ssh = SSHAgentMCP()
result = ssh.execute_command("homelab", "docker ps")
print(result)

# 3. RAG - Buscar documentação
rag = RAGMCP()
results = rag.search("como configurar Docker", collection="homelab")
print(results)

# 4. Homelab - Status de serviços
homelab = HomelabMCP()
status = homelab.docker_ps()
print(status)

# 5. Funções rápidas
output = quick_ssh("uptime")
print(output)

results = quick_github_search("def main", repo="eddie-auto-dev")
print(results)

docs = quick_rag_search("MCP server configuration")
print(docs)
""")


# ============================================================================
# CLI para uso standalone
# ============================================================================

def main():
    """Interface CLI"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Helper CLI")
    parser.add_argument("server", choices=["github", "ssh", "rag", "homelab"], help="MCP Server")
    parser.add_argument("--tool", help="Nome da ferramenta")
    parser.add_argument("--params", help="Parâmetros JSON", default="{}")
    parser.add_argument("--list", action="store_true", help="Listar ferramentas")
    parser.add_argument("--examples", action="store_true", help="Mostrar exemplos")

    args = parser.parse_args()

    if args.examples:
        examples()
        return

    client = MCPClient(args.server)

    if args.list:
        tools = client.list_tools()
        print(f"\nFerramentas disponíveis no servidor '{args.server}':")
        for tool in tools:
            print(f"  - {tool}")
        return

    if not args.tool:
        print("Erro: --tool é obrigatório")
        parser.print_help()
        return

    try:
        params = json.loads(args.params)
    except:
        print("Erro: --params deve ser JSON válido")
        return

    result = client.execute(args.tool, params)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Modo interativo se sem argumentos
        examples()
    else:
        main()

