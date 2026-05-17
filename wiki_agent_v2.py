#!/usr/bin/env python3
"""
Wiki RPA4All Agent v2 - Criar páginas com GraphQL variables (sem escaping issues)
Problema v1: Escaping de strings em GraphQL mutation
Solução v2: Usar GraphQL variables + separar query de variables
"""

import requests
import json
import sys
from typing import Dict, List, Tuple

WIKI_API = "http://192.168.15.2:3009/graphql"
WIKI_PUBLIC = "https://wiki.rpa4all.com"

class WikiAgent:
    def __init__(self):
        self.created = 0
        self.failed = 0

    def create_page(self, path: str, title: str, description: str,
                   content: str, tags: List[str]) -> bool:
        """Criar página usando GraphQL variables (CORRETO)"""

        # GraphQL query com variables
        query = """
        mutation CreatePage($content: String!, $title: String!, $path: String!,
                           $description: String, $tags: [String]) {
          pages {
            create(
              content: $content
              title: $title
              path: $path
              description: $description
              editor: "markdown"
              isPublished: true
              isPrivate: false
              locale: "pt"
              tags: $tags
            ) {
              responseResult {
                succeeded
                errorCode
                message
              }
              page {
                id
                path
                title
              }
            }
          }
        }
        """

        # Variables separadas (escaping automático)
        variables = {
            "content": content,
            "title": title,
            "path": path,
            "description": description,
            "tags": tags
        }

        try:
            response = requests.post(
                WIKI_API,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
                timeout=20
            )

            result = response.json()

            # Verificar erros GraphQL
            if "errors" in result and result["errors"]:
                error = result["errors"][0].get("message", "Erro desconhecido")
                print(f"   ❌ Erro GraphQL: {error}")
                return False

            # Verificar resultado
            page_result = result.get("data", {}).get("pages", {}).get("create", {})
            response_result = page_result.get("responseResult", {})

            if response_result.get("succeeded"):
                page_data = page_result.get("page", {})
                page_id = page_data.get("id", "?")
                print(f"   ✅ Criada!")
                print(f"      ID: {page_id}")
                print(f"      URL: {WIKI_PUBLIC}/{path}")
                self.created += 1
                return True
            else:
                message = response_result.get("message", "Erro desconhecido")
                error_code = response_result.get("errorCode", "?")
                print(f"   ❌ Falha: {message} ({error_code})")
                self.failed += 1
                return False

        except Exception as e:
            print(f"   ❌ Exceção: {str(e)}")
            self.failed += 1
            return False

    def run(self, pages_config: List[Dict]) -> Tuple[int, int]:
        """Executar criação de todas as páginas"""

        print("🚀 Wiki Agent v2 - Criar Páginas")
        print("=" * 70)

        for page_config in pages_config:
            print(f"\n📝 {page_config['title']}")
            print(f"   Path: {page_config['path']}")

            # Ler arquivo
            try:
                with open(page_config['file'], 'r', encoding='utf-8') as f:
                    content = f.read()
            except FileNotFoundError:
                print(f"   ❌ Arquivo não encontrado: {page_config['file']}")
                self.failed += 1
                continue

            # Criar página
            self.create_page(
                path=page_config['path'],
                title=page_config['title'],
                description=page_config['description'],
                content=content,
                tags=page_config['tags']
            )

        # Resumo
        print(f"\n{'=' * 70}")
        print(f"Resultado: {self.created} criadas | {self.failed} falhadas")
        print(f"{'=' * 70}")

        return self.created, self.failed


if __name__ == "__main__":
    pages = [
        {
            "file": "/workspace/eddie-auto-dev/wiki_conversas-review-2026-05-01-05.md",
            "path": "project-overview/conversas-review-2026-05-01-05",
            "title": "Revisão de Conversas: 2026-05-01 a 2026-05-05",
            "description": "53 commits em 5 dias cobrindo Nextcloud VPN, Authentik migration, CI fixes, RPA4All monitoring, Trading guardrails",
            "tags": ["project", "review", "2026-05", "conversas", "retrospective"]
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_authentik-secrets-migration.md",
            "path": "infrastructure/authentik-secrets-migration",
            "title": "Authentik as Secrets Backend",
            "description": "Migração de Bitwarden para Authentik como backend primário com OIDC",
            "tags": ["authentik", "secrets", "oidc", "oauth2", "infrastructure", "migration"]
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_nextcloud-vpn-setup.md",
            "path": "operations/nextcloud-vpn-setup",
            "title": "Nextcloud VPN Setup & Watchdog",
            "description": "VPN on-demand com watchdog auto up/down, Cloudflare bypass, Files API",
            "tags": ["nextcloud", "vpn", "automation", "backup", "operations"]
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_rpa4all-monitoring.md",
            "path": "operations/rpa4all-snapshot-monitoring",
            "title": "RPA4All Snapshot Monitoring",
            "description": "Primeira observabilidade em produção do RPA4All com Watchdog + Prometheus + Grafana",
            "tags": ["rpa4all", "monitoring", "observability", "prometheus", "grafana", "alerts"]
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_trading-guardrails.md",
            "path": "trading/guardrails-tuning",
            "title": "Trading Guardrails Tuning & Rebuy Lock",
            "description": "Guardrails tuning progressivo (1% → 0.5% → 0.3%), per-slot positions, rebuy lock strict",
            "tags": ["trading", "kucoin", "guardrails", "risk-management", "tuning"]
        }
    ]

    agent = WikiAgent()
    created, failed = agent.run(pages)

    sys.exit(0 if failed == 0 else 1)
