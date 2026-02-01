#!/usr/bin/env python3
"""
GitHub Agent Server - Servidor Web com Autenticação OAuth
Um agente autônomo que conecta com GitHub via OAuth ou Token
"""

import os
import json
import secrets
import requests
from pathlib import Path
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
from flask_cors import CORS

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# Diretório base
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / ".github_agent_config.json"

# Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "192.168.15.2")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "codestral:22b")

# GitHub OAuth - Você precisa criar um OAuth App no GitHub
# https://github.com/settings/developers -> OAuth Apps -> New OAuth App
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:5000/callback")

# Flask
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
CORS(app)

# =============================================================================
# GERENCIAMENTO DE CONFIGURAÇÃO
# =============================================================================


def load_config():
    """Carrega configuração do arquivo"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config):
    """Salva configuração no arquivo"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    # Protege o arquivo
    os.chmod(CONFIG_FILE, 0o600)


def get_github_token():
    """Obtém token do GitHub da sessão ou config"""
    # Primeiro tenta da sessão
    if "github_token" in session:
        return session["github_token"]
    # Next, try retrieving from a Vaultwarden / Bitwarden CLI if enabled.
    # Configure via env: VAULTWARDEN_ENABLED=1, VAULTWARDEN_URL or BW_SERVER, and BW_SESSION must be set.
    try:
        import shutil
        import subprocess
        import json as _json

        if os.getenv("VAULTWARDEN_ENABLED", "").lower() in ("1", "true", "yes"):
            bw = shutil.which("bw")
            bw_server = os.getenv("BW_SERVER") or os.getenv("VAULTWARDEN_URL")
            bw_session = os.getenv("BW_SESSION")
            item_name = os.getenv(
                "GITHUB_TOKEN_ITEM_NAME", "GitHub Personal Access Token (deploy)"
            )
            if bw and bw_session:
                env = os.environ.copy()
                if bw_server:
                    env["BW_SERVER"] = bw_server
                # Try to find item by search (returns list)
                try:
                    p = subprocess.run(
                        [bw, "list", "items", "--search", item_name],
                        capture_output=True,
                        text=True,
                        env=env,
                        timeout=15,
                    )
                    if p.returncode == 0 and p.stdout:
                        items = _json.loads(p.stdout)
                        if isinstance(items, list) and items:
                            item = items[0]
                            item_id = item.get("id")
                            if item_id:
                                q = subprocess.run(
                                    [bw, "get", "item", item_id],
                                    capture_output=True,
                                    text=True,
                                    env=env,
                                    timeout=15,
                                )
                                if q.returncode == 0 and q.stdout:
                                    j = _json.loads(q.stdout)
                                    # Common locations: login.password or fields[]
                                    token = None
                                    login = j.get("login") or {}
                                    token = login.get("password")
                                    if not token:
                                        for f in j.get("fields", []):
                                            name = f.get("name", "").lower()
                                            if name in (
                                                "token",
                                                "password",
                                                "github_token",
                                                "pat",
                                            ):
                                                token = f.get("value")
                                                break
                                    if token:
                                        return token
                except Exception:
                    pass
    except Exception:
        pass

    # Depois do arquivo de config
    config = load_config()
    return config.get("github_token", "")


def set_github_token(token, user_info=None):
    """Salva token do GitHub"""
    session["github_token"] = token
    config = load_config()
    config["github_token"] = token
    config["token_set_at"] = datetime.now().isoformat()
    if user_info:
        config["github_user"] = user_info
    save_config(config)


def clear_github_token():
    """Remove token do GitHub"""
    session.pop("github_token", None)
    config = load_config()
    config.pop("github_token", None)
    config.pop("github_user", None)
    save_config(config)


# =============================================================================
# CLIENTES API
# =============================================================================


class GitHubClient:
    """Cliente para API do GitHub"""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        url = f"https://api.github.com{endpoint}"
        try:
            response = requests.request(
                method, url, headers=self.headers, json=data, timeout=30
            )
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {"error": str(e)}

    def get_user(self):
        return self._request("GET", "/user")

    def list_repos(self, username=None, org=None, per_page=30):
        if org:
            return self._request("GET", f"/orgs/{org}/repos?per_page={per_page}")
        elif username:
            return self._request("GET", f"/users/{username}/repos?per_page={per_page}")
        return self._request("GET", f"/user/repos?per_page={per_page}")

    def get_repo(self, owner, repo):
        return self._request("GET", f"/repos/{owner}/{repo}")

    def list_issues(self, owner, repo, state="open"):
        return self._request("GET", f"/repos/{owner}/{repo}/issues?state={state}")

    def create_issue(self, owner, repo, title, body=""):
        return self._request(
            "POST", f"/repos/{owner}/{repo}/issues", {"title": title, "body": body}
        )

    def list_prs(self, owner, repo, state="open"):
        return self._request("GET", f"/repos/{owner}/{repo}/pulls?state={state}")

    def list_branches(self, owner, repo):
        return self._request("GET", f"/repos/{owner}/{repo}/branches")

    def list_commits(self, owner, repo, per_page=20):
        return self._request(
            "GET", f"/repos/{owner}/{repo}/commits?per_page={per_page}"
        )

    def search_repos(self, query):
        return self._request("GET", f"/search/repositories?q={query}")


class OllamaClient:
    """Cliente para Ollama"""

    def __init__(self):
        self.base_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
        self.model = OLLAMA_MODEL

    def chat(self, messages):
        url = f"{self.base_url}/v1/chat/completions"
        try:
            response = requests.post(
                url,
                json={"model": self.model, "messages": messages, "temperature": 0.1},
                timeout=120,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Erro Ollama: {e}"

    def generate(self, prompt, system=None):
        url = f"{self.base_url}/api/generate"
        data = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            data["system"] = system
        try:
            response = requests.post(url, json=data, timeout=120)
            return response.json().get("response", "")
        except Exception as e:
            return f"Erro: {e}"


# =============================================================================
# AGENTE GITHUB
# =============================================================================


class GitHubAgent:
    """Agente que processa comandos em linguagem natural"""

    SYSTEM_PROMPT = """Você é um assistente de GitHub. Analise o pedido e retorne APENAS JSON:
{
    "action": "<ação>",
    "params": {<parâmetros>},
    "confidence": <0.0-1.0>
}

Ações: list_repos, get_repo, list_issues, create_issue, list_prs, list_branches, list_commits, get_user, search_repos, unknown

Params por ação:
- list_repos: username?, org?
- get_repo: owner, repo
- list_issues: owner, repo, state?
- create_issue: owner, repo, title, body?
- list_prs: owner, repo, state?
- list_branches: owner, repo
- list_commits: owner, repo
- get_user: username?
- search_repos: query

Responda APENAS com JSON válido."""

    def __init__(self, github_token):
        self.ollama = OllamaClient()
        self.github = GitHubClient(github_token)

    def parse_intent(self, user_input):
        response = self.ollama.chat(
            [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ]
        )

        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1].replace("json", "").strip()
            return json.loads(json_str)
        except:
            return {"action": "unknown", "params": {}, "confidence": 0}

    def execute(self, intent):
        action = intent.get("action", "unknown")
        p = intent.get("params", {})

        actions = {
            "list_repos": lambda: self.github.list_repos(
                p.get("username"), p.get("org")
            ),
            "get_repo": lambda: self.github.get_repo(p["owner"], p["repo"]),
            "list_issues": lambda: self.github.list_issues(
                p["owner"], p["repo"], p.get("state", "open")
            ),
            "create_issue": lambda: self.github.create_issue(
                p["owner"], p["repo"], p["title"], p.get("body", "")
            ),
            "list_prs": lambda: self.github.list_prs(
                p["owner"], p["repo"], p.get("state", "open")
            ),
            "list_branches": lambda: self.github.list_branches(p["owner"], p["repo"]),
            "list_commits": lambda: self.github.list_commits(p["owner"], p["repo"]),
            "get_user": lambda: (
                self.github.get_user()
                if not p.get("username")
                else self.github._request("GET", f"/users/{p['username']}")
            ),
            "search_repos": lambda: self.github.search_repos(p["query"]),
        }

        if action in actions:
            try:
                return actions[action]()
            except KeyError as e:
                return {"error": f"Parâmetro faltando: {e}"}
        return {"error": "Ação não reconhecida"}

    def format_response(self, action, data):
        if isinstance(data, dict) and "error" in data:
            return data

        data_str = json.dumps(data, ensure_ascii=False)[:3000]
        prompt = f"Formate estes dados do GitHub de forma clara em português, use markdown:\n\nAção: {action}\nDados: {data_str}"

        formatted = self.ollama.generate(prompt)
        return {"formatted": formatted, "raw": data}

    def process(self, user_input):
        intent = self.parse_intent(user_input)

        if intent.get("action") == "unknown" or intent.get("confidence", 0) < 0.3:
            return {
                "success": False,
                "message": "Não entendi o pedido. Tente algo como: 'Liste meus repositórios' ou 'Mostre issues do microsoft/vscode'",
            }

        result = self.execute(intent)
        formatted = self.format_response(intent["action"], result)

        return {"success": True, "intent": intent, "result": formatted}


# =============================================================================
# ROTAS WEB
# =============================================================================


@app.route("/")
def index():
    """Página principal"""
    config = load_config()
    github_user = config.get("github_user")
    has_token = bool(get_github_token())
    has_oauth = bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)

    return render_template(
        "index.html",
        github_user=github_user,
        has_token=has_token,
        has_oauth=has_oauth,
        ollama_host=OLLAMA_HOST,
        ollama_port=OLLAMA_PORT,
        ollama_model=OLLAMA_MODEL,
    )


@app.route("/portal")
def portal():
    """Portal unificado com abas embutidas para as UIs internas"""
    interceptor = os.environ.get(
        "INTERCEPTOR_PUBLIC_URL",
        os.environ.get("DASHBOARD_URL", "http://localhost:8501"),
    )
    openwebui = os.environ.get("OPENWEBUI_URL", "http://192.168.15.2:3000")
    diretor_ui = os.environ.get("DIRETOR_UI_URL", openwebui)
    # github agent external URL (assume same host)
    github_agent = request.host_url.rstrip("/")

    return render_template(
        "portal.html",
        interceptor_url=interceptor,
        openwebui=openwebui,
        diretor_ui=diretor_ui,
        github_agent=github_agent,
    )


@app.route("/portal/notify", methods=["POST"])
def portal_notify():
    """Publish a request to the DIRETOR and return immediately."""
    try:
        # Use helper to publish to bus (tools/invoke_director.py logic)
        import subprocess
        import shlex

        message = f"Por favor, DIRETOR: autorize e avalie a exposição do Portal unificado em {request.host_url}portal"
        cmd = f"python3 tools/invoke_director.py {shlex.quote(message)}"
        subprocess.Popen(cmd, shell=True)
        return jsonify({"ok": True, "message": "Solicitação enviada ao DIRETOR"})
    except Exception as e:
        return jsonify({"ok": False, "message": f"Erro ao notificar DIRETOR: {e}"}), 500


@app.route("/login/github")
def github_login():
    """Inicia OAuth do GitHub"""
    if not GITHUB_CLIENT_ID:
        flash("OAuth não configurado. Use token manual.", "error")
        return redirect(url_for("index"))

    state = secrets.token_hex(16)
    session["oauth_state"] = state

    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_REDIRECT_URI}"
        f"&scope=repo,read:user,read:org"
        f"&state={state}"
    )
    return redirect(auth_url)


@app.route("/callback")
def github_callback():
    """Callback do OAuth do GitHub"""
    error = request.args.get("error")
    if error:
        flash(f"Erro no login: {error}", "error")
        return redirect(url_for("index"))

    code = request.args.get("code")
    state = request.args.get("state")

    if state != session.get("oauth_state"):
        flash("Estado inválido. Tente novamente.", "error")
        return redirect(url_for("index"))

    # Troca code por token
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI,
        },
    )

    data = response.json()
    token = data.get("access_token")

    if not token:
        flash(
            f"Erro ao obter token: {data.get('error_description', 'Desconhecido')}",
            "error",
        )
        return redirect(url_for("index"))

    # Obtém info do usuário
    github = GitHubClient(token)
    user_info = github.get_user()

    set_github_token(token, user_info)
    flash(
        f"Login realizado com sucesso! Bem-vindo, {user_info.get('login', 'usuário')}!",
        "success",
    )

    return redirect(url_for("index"))


@app.route("/login/token", methods=["POST"])
def token_login():
    """Login via token manual"""
    token = request.form.get("token", "").strip()

    if not token:
        flash("Token não fornecido", "error")
        return redirect(url_for("index"))

    # Valida token
    github = GitHubClient(token)
    user_info = github.get_user()

    if "error" in user_info:
        flash(f"Token inválido: {user_info['error']}", "error")
        return redirect(url_for("index"))

    set_github_token(token, user_info)
    flash(
        f"Token configurado! Bem-vindo, {user_info.get('login', 'usuário')}!", "success"
    )

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    """Logout"""
    clear_github_token()
    flash("Desconectado com sucesso!", "success")
    return redirect(url_for("index"))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """API para processar comandos"""
    token = get_github_token()
    if not token:
        return jsonify({"success": False, "message": "Faça login no GitHub primeiro"})

    data = request.json
    user_input = data.get("message", "")

    if not user_input:
        return jsonify({"success": False, "message": "Mensagem vazia"})

    agent = GitHubAgent(token)
    result = agent.process(user_input)

    return jsonify(result)


@app.route("/api/status")
def api_status():
    """Status do servidor"""
    token = get_github_token()
    config = load_config()

    # Testa Ollama
    ollama_ok = False
    try:
        r = requests.get(f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags", timeout=5)
        ollama_ok = r.status_code == 200
    except:
        pass

    return jsonify(
        {
            "github_connected": bool(token),
            "github_user": config.get("github_user", {}).get("login"),
            "ollama_connected": ollama_ok,
            "ollama_host": OLLAMA_HOST,
            "ollama_model": OLLAMA_MODEL,
        }
    )


@app.route("/api/quick/<action>")
def api_quick_action(action):
    """Ações rápidas sem usar LLM"""
    token = get_github_token()
    if not token:
        return jsonify({"error": "Não autenticado"})

    github = GitHubClient(token)

    if action == "repos":
        return jsonify(github.list_repos())
    elif action == "user":
        return jsonify(github.get_user())

    return jsonify({"error": "Ação desconhecida"})


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Cria pasta de templates se não existir
    templates_dir = BASE_DIR / "templates"
    templates_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("🤖 GitHub Agent Server")
    print("=" * 60)
    print(f"📡 Ollama: http://{OLLAMA_HOST}:{OLLAMA_PORT}")
    print(f"🧠 Modelo: {OLLAMA_MODEL}")
    print(f"🔐 OAuth: {'Configurado' if GITHUB_CLIENT_ID else 'Não configurado'}")
    print("-" * 60)
    print("🌐 Servidor: http://localhost:5000")
    print("=" * 60)

    app.run(host="0.0.0.0", port=5000, debug=True)
