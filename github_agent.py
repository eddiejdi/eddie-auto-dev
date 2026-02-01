#!/usr/bin/env python3
"""
GitHub Agent para Ollama
Um agente que integra seu servidor Llama com a API do GitHub
para executar comandos como: listar repos, criar issues, ver PRs, etc.
"""

import os
import json
import requests
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "192.168.15.2")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "codestral:22b")

# Token do GitHub - defina como variável de ambiente
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"

# =============================================================================
# CLASSES DE SUPORTE
# =============================================================================


class GitHubAction(Enum):
    LIST_REPOS = "list_repos"
    GET_REPO = "get_repo"
    LIST_ISSUES = "list_issues"
    CREATE_ISSUE = "create_issue"
    GET_ISSUE = "get_issue"
    LIST_PRS = "list_prs"
    GET_PR = "get_pr"
    LIST_BRANCHES = "list_branches"
    SEARCH_CODE = "search_code"
    GET_USER = "get_user"
    LIST_COMMITS = "list_commits"
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    action: GitHubAction
    params: Dict[str, Any]
    confidence: float


# =============================================================================
# CLIENTE GITHUB
# =============================================================================


class GitHubClient:
    """Cliente para interagir com a API do GitHub"""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Faz uma requisição à API do GitHub"""
        url = f"{GITHUB_API}{endpoint}"
        try:
            response = requests.request(
                method, url, headers=self.headers, json=data, timeout=30
            )
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def list_repos(self, username: str = None, org: str = None) -> List[dict]:
        """Lista repositórios do usuário ou organização"""
        if org:
            return self._request("GET", f"/orgs/{org}/repos")
        elif username:
            return self._request("GET", f"/users/{username}/repos")
        else:
            return self._request("GET", "/user/repos")

    def get_repo(self, owner: str, repo: str) -> dict:
        """Obtém detalhes de um repositório"""
        return self._request("GET", f"/repos/{owner}/{repo}")

    def list_issues(self, owner: str, repo: str, state: str = "open") -> List[dict]:
        """Lista issues de um repositório"""
        return self._request("GET", f"/repos/{owner}/{repo}/issues?state={state}")

    def create_issue(self, owner: str, repo: str, title: str, body: str = "") -> dict:
        """Cria uma nova issue"""
        return self._request(
            "POST", f"/repos/{owner}/{repo}/issues", {"title": title, "body": body}
        )

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        """Obtém detalhes de uma issue específica"""
        return self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")

    def list_prs(self, owner: str, repo: str, state: str = "open") -> List[dict]:
        """Lista pull requests de um repositório"""
        return self._request("GET", f"/repos/{owner}/{repo}/pulls?state={state}")

    def get_pr(self, owner: str, repo: str, pr_number: int) -> dict:
        """Obtém detalhes de um pull request"""
        return self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")

    def list_branches(self, owner: str, repo: str) -> List[dict]:
        """Lista branches de um repositório"""
        return self._request("GET", f"/repos/{owner}/{repo}/branches")

    def search_code(self, query: str, repo: str = None) -> dict:
        """Busca código no GitHub"""
        q = f"{query} repo:{repo}" if repo else query
        return self._request("GET", f"/search/code?q={q}")

    def get_user(self, username: str = None) -> dict:
        """Obtém informações do usuário"""
        if username:
            return self._request("GET", f"/users/{username}")
        return self._request("GET", "/user")

    def list_commits(self, owner: str, repo: str, branch: str = None) -> List[dict]:
        """Lista commits de um repositório"""
        endpoint = f"/repos/{owner}/{repo}/commits"
        if branch:
            endpoint += f"?sha={branch}"
        return self._request("GET", endpoint)


# =============================================================================
# CLIENTE OLLAMA
# =============================================================================


class OllamaClient:
    """Cliente para interagir com o servidor Ollama"""

    def __init__(self, host: str, port: str, model: str):
        self.base_url = f"http://{host}:{port}"
        self.model = model

    def generate(self, prompt: str, system: str = None) -> str:
        """Gera uma resposta usando o modelo"""
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if system:
            data["system"] = system

        try:
            response = requests.post(url, json=data, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            return f"Erro ao conectar com Ollama: {e}"

    def chat(self, messages: List[dict]) -> str:
        """Chat com o modelo usando formato de mensagens"""
        url = f"{self.base_url}/v1/chat/completions"
        data = {"model": self.model, "messages": messages, "temperature": 0.1}

        try:
            response = requests.post(url, json=data, timeout=120)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Erro ao conectar com Ollama: {e}"


# =============================================================================
# AGENTE GITHUB
# =============================================================================


class GitHubAgent:
    """Agente que processa comandos em linguagem natural para o GitHub"""

    SYSTEM_PROMPT = """Você é um assistente especializado em GitHub. 
Sua função é analisar pedidos do usuário e identificar qual ação do GitHub deve ser executada.

Você deve responder APENAS em formato JSON com a seguinte estrutura:
{
    "action": "<ação>",
    "params": {<parâmetros necessários>},
    "confidence": <0.0 a 1.0>
}

Ações disponíveis:
- list_repos: Listar repositórios (params: username ou org, opcional)
- get_repo: Detalhes de um repo (params: owner, repo)
- list_issues: Listar issues (params: owner, repo, state=open/closed/all)
- create_issue: Criar issue (params: owner, repo, title, body)
- get_issue: Ver uma issue (params: owner, repo, issue_number)
- list_prs: Listar PRs (params: owner, repo, state=open/closed/all)
- get_pr: Ver um PR (params: owner, repo, pr_number)
- list_branches: Listar branches (params: owner, repo)
- search_code: Buscar código (params: query, repo opcional)
- get_user: Info do usuário (params: username opcional)
- list_commits: Listar commits (params: owner, repo, branch opcional)

Se não conseguir identificar a ação, use action="unknown".
Responda APENAS com o JSON, sem explicações adicionais."""

    def __init__(self):
        self.ollama = OllamaClient(OLLAMA_HOST, OLLAMA_PORT, OLLAMA_MODEL)
        self.github = GitHubClient(GITHUB_TOKEN)

    def parse_intent(self, user_input: str) -> ParsedIntent:
        """Usa o LLM para entender a intenção do usuário"""
        response = self.ollama.chat(
            [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ]
        )

        try:
            # Tenta extrair JSON da resposta
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str)
            action = GitHubAction(data.get("action", "unknown"))
            return ParsedIntent(
                action=action,
                params=data.get("params", {}),
                confidence=data.get("confidence", 0.5),
            )
        except (json.JSONDecodeError, ValueError):
            return ParsedIntent(
                action=GitHubAction.UNKNOWN,
                params={"raw_response": response},
                confidence=0.0,
            )

    def execute_action(self, intent: ParsedIntent) -> dict:
        """Executa a ação identificada"""
        p = intent.params

        actions = {
            GitHubAction.LIST_REPOS: lambda: self.github.list_repos(
                username=p.get("username"), org=p.get("org")
            ),
            GitHubAction.GET_REPO: lambda: self.github.get_repo(p["owner"], p["repo"]),
            GitHubAction.LIST_ISSUES: lambda: self.github.list_issues(
                p["owner"], p["repo"], p.get("state", "open")
            ),
            GitHubAction.CREATE_ISSUE: lambda: self.github.create_issue(
                p["owner"], p["repo"], p["title"], p.get("body", "")
            ),
            GitHubAction.GET_ISSUE: lambda: self.github.get_issue(
                p["owner"], p["repo"], p["issue_number"]
            ),
            GitHubAction.LIST_PRS: lambda: self.github.list_prs(
                p["owner"], p["repo"], p.get("state", "open")
            ),
            GitHubAction.GET_PR: lambda: self.github.get_pr(
                p["owner"], p["repo"], p["pr_number"]
            ),
            GitHubAction.LIST_BRANCHES: lambda: self.github.list_branches(
                p["owner"], p["repo"]
            ),
            GitHubAction.SEARCH_CODE: lambda: self.github.search_code(
                p["query"], p.get("repo")
            ),
            GitHubAction.GET_USER: lambda: self.github.get_user(p.get("username")),
            GitHubAction.LIST_COMMITS: lambda: self.github.list_commits(
                p["owner"], p["repo"], p.get("branch")
            ),
        }

        if intent.action in actions:
            try:
                return actions[intent.action]()
            except KeyError as e:
                return {"error": f"Parâmetro obrigatório faltando: {e}"}

        return {"error": "Ação não reconhecida", "intent": str(intent)}

    def format_response(self, action: GitHubAction, data: Any) -> str:
        """Usa o LLM para formatar a resposta de forma amigável"""
        if isinstance(data, dict) and "error" in data:
            return f"❌ Erro: {data['error']}"

        # Limita o tamanho dos dados para o LLM
        data_str = json.dumps(data, indent=2, ensure_ascii=False)
        if len(data_str) > 4000:
            data_str = data_str[:4000] + "\n... (truncado)"

        prompt = f"""Formate os seguintes dados do GitHub de forma clara e amigável em português.
Use emojis para deixar mais visual. Seja conciso.

Ação executada: {action.value}
Dados:
{data_str}

Responda em português brasileiro:"""

        return self.ollama.generate(prompt)

    def process(self, user_input: str) -> str:
        """Processa um comando do usuário"""
        print(f"🤔 Analisando: {user_input}")

        # 1. Entender a intenção
        intent = self.parse_intent(user_input)
        print(
            f"📋 Ação identificada: {intent.action.value} (confiança: {intent.confidence:.0%})"
        )

        if intent.action == GitHubAction.UNKNOWN:
            return "❌ Não consegui entender o que você quer fazer. Tente reformular o pedido."

        if intent.confidence < 0.5:
            return f"⚠️ Não tenho certeza do que fazer. Entendi: {intent.action.value} com {intent.params}"

        # 2. Executar a ação
        print(f"⚡ Executando: {intent.action.value} com params: {intent.params}")
        result = self.execute_action(intent)

        # 3. Formatar resposta
        return self.format_response(intent.action, result)


# =============================================================================
# INTERFACE DE LINHA DE COMANDO
# =============================================================================


def interactive_mode():
    """Modo interativo do agente"""
    print("=" * 60)
    print("🤖 GitHub Agent - Seu assistente GitHub com Ollama")
    print("=" * 60)
    print(f"📡 Servidor Ollama: {OLLAMA_HOST}:{OLLAMA_PORT}")
    print(f"🧠 Modelo: {OLLAMA_MODEL}")
    print(
        f"🔑 GitHub Token: {'✅ Configurado' if GITHUB_TOKEN else '❌ Não configurado'}"
    )
    print("-" * 60)
    print("Exemplos de comandos:")
    print("  • 'Liste meus repositórios'")
    print("  • 'Mostre as issues abertas do repo microsoft/vscode'")
    print("  • 'Quais são os PRs abertos em facebook/react?'")
    print("  • 'Crie uma issue no meu-user/meu-repo com título Bug encontrado'")
    print("  • 'Mostre os commits recentes de torvalds/linux'")
    print("-" * 60)
    print("Digite 'sair' para encerrar.\n")

    if not GITHUB_TOKEN:
        print("⚠️  AVISO: Configure GITHUB_TOKEN para acesso completo à API")
        print("   export GITHUB_TOKEN='seu_token_aqui'\n")

    agent = GitHubAgent()

    while True:
        try:
            user_input = input("🧑 Você: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("👋 Até mais!")
                break

            response = agent.process(user_input)
            print(f"\n🤖 Agente:\n{response}\n")
            print("-" * 60)

        except KeyboardInterrupt:
            print("\n👋 Até mais!")
            break
        except Exception as e:
            print(f"❌ Erro: {e}\n")


def single_command(command: str):
    """Executa um único comando"""
    agent = GitHubAgent()
    response = agent.process(command)
    print(response)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Modo de comando único
        command = " ".join(sys.argv[1:])
        single_command(command)
    else:
        # Modo interativo
        interactive_mode()
