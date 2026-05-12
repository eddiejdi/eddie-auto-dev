#!/usr/bin/env python3
"""
Wiki RPA4All Agent v3 - Inteligente com Ollama
- Lê .md puros
- Usa Ollama (coordinator 192.168.15.2:11437) para processar
- Gera titles, descriptions, tags otimizadas com IA
- Cria páginas na wiki com conteúdo estruturado
"""

import requests
import json
import sys
from typing import Dict, List, Tuple

WIKI_API = "http://192.168.15.2:3009/graphql"
WIKI_PUBLIC = "https://wiki.rpa4all.com"
OLLAMA_API = "http://192.168.15.2:11437/api"

class OllamaProcessor:
    """Usar Ollama para processar conteúdo com IA"""

    @staticmethod
    def process_markdown(content: str, title: str) -> Dict:
        """Processar MD com Ollama para extrair estrutura, summary, tags"""

        prompt = f"""Analise este documento Markdown e extraia:
1. Um resumo executivo (1-2 linhas)
2. 5-8 tags relevantes (separadas por vírgula)
3. Estrutura otimizada do conteúdo

Documento: "{title}"

```markdown
{content[:2000]}
```

Responda em JSON:
{{
  "summary": "resumo de 1-2 linhas",
  "tags": ["tag1", "tag2", "tag3"],
  "structured": true
}}
"""

        try:
            response = requests.post(
                f"{OLLAMA_API}/generate",
                json={
                    "model": "neural-chat",
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3
                },
                timeout=30
            )

            result = response.json()
            response_text = result.get("response", "")

            # Tentar extrair JSON da resposta
            try:
                # Procurar por JSON na resposta
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                    return json.loads(json_str)
            except:
                pass

            # Fallback: retornar estrutura padrão
            return {
                "summary": f"Documentação: {title}",
                "tags": ["auto-generated"],
                "structured": False
            }

        except Exception as e:
            print(f"      ⚠️ Ollama error: {str(e)[:50]}")
            return {
                "summary": f"Documentação: {title}",
                "tags": ["auto-generated"],
                "structured": False
            }


class WikiAgentV3:
    """Wiki Agent v3 - Inteligente com Ollama"""

    def __init__(self):
        self.created = 0
        self.failed = 0
        self.ollama = OllamaProcessor()

        # Obter API key (sem logs/exibição)
        self.api_key = self._get_api_key()

    def _get_api_key(self) -> str:
        """Obter API key do secrets agent"""
        try:
            response = requests.post(
                "http://192.168.15.2:8502/v1/secrets/get",
                json={"name": "wikijs/api_key"},
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value", "")
        except:
            pass
        return ""

    def create_page(self, path: str, title: str, description: str,
                   content: str, tags: List[str]) -> bool:
        """Criar página com GraphQL (sintaxe correta)"""

        query = """
        mutation CreatePage($content: String!, $title: String!, $path: String!,
                           $description: String!, $tags: [String]!) {
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
                error = result["errors"][0].get("message", "Erro")
                print(f"      ❌ {error}")
                return False

            # Verificar resultado
            page_result = result.get("data", {}).get("pages", {}).get("create", {})
            response_result = page_result.get("responseResult", {})

            if response_result.get("succeeded"):
                page_id = page_result.get("page", {}).get("id", "?")
                print(f"      ✅ Criada (ID: {page_id})")
                print(f"      🔗 {WIKI_PUBLIC}/{path}")
                self.created += 1
                return True
            else:
                message = response_result.get("message", "Erro")
                print(f"      ❌ {message}")
                self.failed += 1
                return False

        except Exception as e:
            print(f"      ❌ {str(e)[:60]}")
            self.failed += 1
            return False

    def process_and_create(self, file_path: str, path: str, title: str) -> bool:
        """Ler MD, processar com Ollama, criar página"""

        print(f"\n📝 {title}")
        print(f"   Path: {path}")

        # 1. Ler arquivo
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"   📖 Arquivo lido ({len(content)} bytes)")
        except Exception as e:
            print(f"   ❌ Erro ao ler: {e}")
            self.failed += 1
            return False

        # 2. Processar com Ollama
        print(f"   🤖 Processando com Ollama...")
        metadata = self.ollama.process_markdown(content, title)

        description = metadata.get("summary", f"Documentação: {title}")
        tags = metadata.get("tags", ["auto-generated"])

        print(f"   ✓ Summary: {description[:50]}...")
        print(f"   ✓ Tags: {', '.join(tags[:3])}...")

        # 3. Criar página na wiki
        print(f"   📡 Criando página na wiki...")
        return self.create_page(
            path=path,
            title=title,
            description=description,
            content=content,
            tags=tags
        )

    def run(self, pages_config: List[Dict]) -> Tuple[int, int]:
        """Executar para todas as páginas"""

        print("🚀 Wiki Agent v3 - Inteligente com Ollama")
        print("=" * 70)

        for page in pages_config:
            self.process_and_create(
                file_path=page['file'],
                path=page['path'],
                title=page['title']
            )

        # Resumo
        print(f"\n{'=' * 70}")
        print(f"✅ {self.created} criadas | ❌ {self.failed} falhadas")
        print('=' * 70)

        return self.created, self.failed


if __name__ == "__main__":
    pages = [
        {
            "file": "/workspace/eddie-auto-dev/wiki_conversas-review-2026-05-01-05.md",
            "path": "project-overview/conversas-review-2026-05-01-05",
            "title": "Revisão de Conversas: 2026-05-01 a 2026-05-05"
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_authentik-secrets-migration.md",
            "path": "infrastructure/authentik-secrets-migration",
            "title": "Authentik as Secrets Backend"
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_nextcloud-vpn-setup.md",
            "path": "operations/nextcloud-vpn-setup",
            "title": "Nextcloud VPN Setup & Watchdog"
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_rpa4all-monitoring.md",
            "path": "operations/rpa4all-snapshot-monitoring",
            "title": "RPA4All Snapshot Monitoring"
        },
        {
            "file": "/workspace/eddie-auto-dev/wiki_trading-guardrails.md",
            "path": "trading/guardrails-tuning",
            "title": "Trading Guardrails Tuning & Rebuy Lock"
        }
    ]

    agent = WikiAgentV3()
    created, failed = agent.run(pages)

    sys.exit(0 if failed == 0 else 1)
