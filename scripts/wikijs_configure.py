#!/usr/bin/env python3
"""Script de configuração completa do Wiki.js RPA4All.

Atualiza a welcome page com banner SVG gerado pelo phi4-mini,
configura tema e verifica páginas migradas.
"""

import json
import logging
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

WIKIJS_URL = "http://localhost:3009/graphql"
ADMIN_EMAIL = "admin@rpa4all.com"
ADMIN_PASS = "RPA4All2026!"


def graphql(query: str, variables: dict | None = None, token: str | None = None) -> dict:
    """Executa uma query GraphQL no Wiki.js."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(WIKIJS_URL, data=payload, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        log.error("GraphQL HTTP %d: %s", e.code, e.read().decode()[:300])
        raise
    except URLError as e:
        log.error("Conexão falhou: %s", e.reason)
        raise


def login() -> str:
    """Autentica e retorna JWT."""
    query = """mutation($email: String!, $password: String!) {
        authentication {
            login(username: $email, password: $password, strategy: "local") {
                responseResult { succeeded message }
                jwt
            }
        }
    }"""
    result = graphql(query, {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    login_data = result["data"]["authentication"]["login"]
    if not login_data["responseResult"]["succeeded"]:
        log.error("Login falhou: %s", login_data["responseResult"]["message"])
        sys.exit(1)
    log.info("Login OK — JWT obtido")
    return login_data["jwt"]


def list_pages(token: str) -> list[dict]:
    """Lista todas as páginas existentes."""
    query = """{ pages { list(orderBy: TITLE) { id path title updatedAt } } }"""
    result = graphql(query, token=token)
    return result["data"]["pages"]["list"]


def update_page(token: str, page_id: int, content: str, title: str, description: str, tags: list[str]) -> bool:
    """Atualiza conteúdo de uma página existente."""
    query = """mutation($id: Int!, $content: String!, $title: String!, $description: String!, $tags: [String]!) {
        pages {
            update(id: $id, content: $content, title: $title, description: $description, tags: $tags, isPublished: true, isPrivate: false) {
                responseResult { succeeded message }
            }
        }
    }"""
    variables = {
        "id": page_id,
        "content": content,
        "title": title,
        "description": description,
        "tags": tags,
    }
    result = graphql(query, variables, token)
    resp = result["data"]["pages"]["update"]["responseResult"]
    if resp["succeeded"]:
        log.info("Página #%d '%s' atualizada", page_id, title)
    else:
        log.error("Falha ao atualizar #%d: %s", page_id, resp["message"])
    return resp["succeeded"]


def build_welcome_content(svg_banner: str) -> str:
    """Constrói o conteúdo markdown da welcome page com SVG embutido."""
    return f"""# Bem-vindo ao Wiki RPA4All 🤖

<div style="text-align:center; margin: 20px 0;">

{svg_banner}

</div>

> **Arte gerada por IA** — Banner criado automaticamente com o modelo **phi4-mini** rodando no Ollama local (GPU0).

---

## Sobre Nós

A **RPA4All** é uma empresa focada em automação inteligente, integrando RPA, IA e DevOps para entregar soluções robustas e escaláveis. Este wiki é a central de conhecimento da equipe.

---

## 🔗 Links Rápidos

| Serviço | URL | Descrição |
|---------|-----|-----------|
| 🔐 SSO Authentik | [auth.rpa4all.com](https://auth.rpa4all.com) | Login único para todos os serviços |
| 📚 Wiki.js | [wiki.rpa4all.com](https://wiki.rpa4all.com) | Esta documentação |
| 💬 OpenWebUI | [chat.rpa4all.com](https://chat.rpa4all.com) | Chat com IA (Ollama) |
| 📊 Grafana | [grafana.rpa4all.com](https://grafana.rpa4all.com) | Dashboards e monitoramento |
| 📈 Streamlit | [192.168.15.2:8502](http://192.168.15.2:8502) | Dashboard interativo |
| 🤖 API Agentes | [192.168.15.2:8503](http://192.168.15.2:8503) | API FastAPI dos agentes |
| 🔍 Pi-hole | [192.168.15.2:8080](http://192.168.15.2:8080) | DNS e ad-blocking |
| ☁️ Portainer | [192.168.15.2:9000](http://192.168.15.2:9000) | Gerenciamento Docker |

---

## 📚 Documentação

- [Arquitetura do Sistema](/infraestrutura/arquitetura) — Visão geral da arquitetura multi-agente
- [Guia de Conexão](/infraestrutura/guia-conexao) — Como se conectar à infraestrutura
- [Operações](/infraestrutura/operacoes) — Procedimentos operacionais
- [Eddie - Guia Central](/infraestrutura/eddie-operacoes) — Operações do homelab Eddie
- [Servidor de Email](/infraestrutura/email-server) — Configuração do email server
- [Integrações](/infraestrutura/integracao) — Integrações entre sistemas
- [Visão Geral do Projeto](/projetos/visao-geral) — Overview do projeto principal

---

## 🖥 Homelab Eddie

O homelab **Eddie** é a espinha dorsal da infraestrutura RPA4All:

- **Host**: `192.168.15.2` (Ubuntu Server)
- **GPU0**: NVIDIA RTX 2060 — Ollama porta `11434`
- **GPU1**: NVIDIA GTX 1050 Ti — Ollama porta `11435`
- **VPN**: WireGuard + Cloudflare Tunnel
- **Containers**: 20+ serviços Docker em produção

---

## 🚀 Primeiros Passos (Onboarding)

1. **Acesse o SSO** em [auth.rpa4all.com](https://auth.rpa4all.com) com suas credenciais
2. **Configure a VPN** — solicite o arquivo WireGuard ao admin
3. **Explore o Chat IA** em [chat.rpa4all.com](https://chat.rpa4all.com)
4. **Leia a documentação** começando pela [Arquitetura](/infraestrutura/arquitetura)
5. **Junte-se ao Telegram** — canal da equipe para comunicação

---

*Última atualização automática via script `wikijs_configure.py`*
"""


def main() -> None:
    """Executa a configuração completa do Wiki.js."""
    # 1. Login
    token = login()

    # 2. Listar páginas existentes
    pages = list_pages(token)
    log.info("Páginas encontradas: %d", len(pages))
    for p in pages:
        log.info("  [%d] %s → /%s", p["id"], p["title"], p["path"])

    # 3. Ler SVG do phi4-mini
    svg_path = Path("/tmp/wikijs_banner.svg")
    if svg_path.exists():
        svg_content = svg_path.read_text(encoding="utf-8").strip()
        log.info("SVG carregado: %d bytes", len(svg_content))
    else:
        log.warning("SVG não encontrado em %s, usando fallback", svg_path)
        svg_content = '<svg width="800" height="200" viewBox="0 0 800 200"><rect width="800" height="200" fill="#0f0c29"/><text x="400" y="110" font-size="36" font-weight="bold" fill="#00d4ff" text-anchor="middle" font-family="Arial">RPA4All</text></svg>'

    # 4. Atualizar welcome page
    home_page = next((p for p in pages if p["path"] == "home"), None)
    if home_page:
        welcome_content = build_welcome_content(svg_content)
        update_page(
            token,
            home_page["id"],
            welcome_content,
            "Wiki RPA4All — Página Inicial",
            "Central de conhecimento da RPA4All com documentação, links e guias de onboarding",
            ["home", "rpa4all", "onboarding", "wiki"],
        )
    else:
        log.error("Página 'home' não encontrada!")

    log.info("✅ Configuração concluída!")


if __name__ == "__main__":
    main()
