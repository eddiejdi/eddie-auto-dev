#!/usr/bin/env python3
"""Migra as páginas do Confluence (markdown local) para o Wiki.js via GraphQL API."""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

WIKIJS_URL = "http://192.168.15.2:3009/graphql"
ADMIN_EMAIL = "edenilson.adm@gmail.com"
ADMIN_PASSWORD = sys.argv[1] if len(sys.argv) > 1 else ""

# Mapeamento: arquivo local → (path no wiki, título)
PAGES: list[dict[str, str]] = [
    {
        "file": "docs/confluence/pages/PROJECT_OVERVIEW.md",
        "path": "project-overview",
        "title": "Visão Geral do Projeto",
    },
    {
        "file": "docs/confluence/pages/ARCHITECTURE.md",
        "path": "architecture",
        "title": "Arquitetura Técnica",
    },
    {
        "file": "docs/confluence/pages/OPERATIONS.md",
        "path": "operations",
        "title": "Operações e Runbook",
    },
    {
        "file": "docs/confluence/pages/CONNECTION_GUIDE.md",
        "path": "connection-guide",
        "title": "Guia de Conexão — Shared Homelab",
    },
    {
        "file": "docs/confluence/cloudflare_migration.md",
        "path": "cloudflare-tunnel",
        "title": "Cloudflare Tunnel — Documentação Operacional",
    },
]


def graphql_request(query: str, variables: dict | None = None, token: str = "") -> dict:
    """Executa uma requisição GraphQL no Wiki.js."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(WIKIJS_URL, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def login() -> str:
    """Obtém JWT de autenticação."""
    query = """
    mutation($email: String!, $password: String!) {
      authentication {
        login(username: $email, password: $password, strategy: "local") {
          responseResult { succeeded message }
          jwt
        }
      }
    }
    """
    result = graphql_request(query, {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    login_data = result["data"]["authentication"]["login"]
    if not login_data["responseResult"]["succeeded"]:
        print(f"Erro de login: {login_data['responseResult']['message']}")
        raise SystemExit(1)
    return login_data["jwt"]


def create_page(token: str, title: str, path: str, content: str) -> dict:
    """Cria uma página no Wiki.js."""
    query = """
    mutation($content: String!, $description: String!, $editor: String!,
             $isPublished: Boolean!, $isPrivate: Boolean!, $locale: String!,
             $path: String!, $tags: [String]!, $title: String!) {
      pages {
        create(
          content: $content
          description: $description
          editor: $editor
          isPublished: $isPublished
          isPrivate: $isPrivate
          locale: $locale
          path: $path
          tags: $tags
          title: $title
        ) {
          responseResult { succeeded message }
          page { id title path }
        }
      }
    }
    """
    variables = {
        "content": content,
        "description": f"Migrado do Confluence - {title}",
        "editor": "markdown",
        "isPublished": True,
        "isPrivate": False,
        "locale": "en",
        "path": path,
        "tags": ["confluence", "migração"],
        "title": title,
    }
    return graphql_request(query, variables, token)


def main() -> None:
    """Executa a migração de todas as páginas."""
    if not ADMIN_PASSWORD:
        print("Uso: python migrate_confluence_to_wikijs.py <admin_password>")
        raise SystemExit(1)

    root = Path(__file__).resolve().parent.parent
    print("=== Migração Confluence → Wiki.js ===\n")

    # Login
    print("Autenticando...")
    token = login()
    print("Login OK\n")

    # Migrar cada página
    ok_count = 0
    for page_info in PAGES:
        filepath = root / page_info["file"]
        if not filepath.exists():
            print(f"SKIP: {page_info['file']} não encontrado")
            continue

        content = filepath.read_text(encoding="utf-8")
        print(f"Criando: {page_info['title']} → /{page_info['path']}")

        try:
            result = create_page(token, page_info["title"], page_info["path"], content)
            page_data = result.get("data", {}).get("pages", {}).get("create", {})
            resp = page_data.get("responseResult", {})
            if resp.get("succeeded"):
                page = page_data.get("page", {})
                print(f"  OK (id={page.get('id')})")
                ok_count += 1
            else:
                print(f"  ERRO: {resp.get('message', 'resposta inesperada')}")
        except urllib.error.HTTPError as e:
            print(f"  HTTP ERROR {e.code}: {e.read().decode()[:200]}")
        except Exception as e:
            print(f"  ERRO: {e}")

    print(f"\n=== Resultado: {ok_count}/{len(PAGES)} páginas migradas ===")
    if ok_count < len(PAGES):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
