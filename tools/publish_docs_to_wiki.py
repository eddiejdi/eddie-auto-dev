#!/usr/bin/env python3
"""
Publicar documentação local para Wiki.js
Requer: WIKI_API_KEY e WIKI_URL em env vars ou config
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# Configuração
WIKI_URL = os.getenv("WIKI_URL", "http://127.0.0.1:3009")
WIKI_API_KEY = os.getenv("WIKI_API_KEY", "")

# GraphQL mutation para criar/atualizar página
CREATE_PAGE_MUTATION = """
mutation CreatePage($input: PageCreateInput!) {
  pages {
    create(input: $input) {
      id
      title
      path
      isPublished
    }
  }
}
"""

def get_graphql_headers():
    """Preparar headers para requisição GraphQL"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WIKI_API_KEY}" if WIKI_API_KEY else ""
    }

def publish_doc(doc_path: str, wiki_path: str, title: str) -> bool:
    """
    Publicar documento local para Wiki.js
    
    Args:
        doc_path: Caminho local do arquivo MD
        wiki_path: Caminho na wiki (ex: "docs/operational-status")
        title: Título da página
    
    Returns:
        True se sucesso, False se falha
    """
    try:
        # Ler arquivo
        doc_file = Path(doc_path)
        if not doc_file.exists():
            print(f"❌ Arquivo não encontrado: {doc_path}")
            return False
        
        content = doc_file.read_text(encoding='utf-8')
        
        # Preparar payload GraphQL
        variables = {
            "input": {
                "title": title,
                "description": f"Publicado em {datetime.now().isoformat()}",
                "isPublished": True,
                "isPrivate": False,
                "locale": "pt-BR",
                "path": wiki_path,
                "content": content,
                "editor": "markdown"
            }
        }
        
        payload = {
            "query": CREATE_PAGE_MUTATION,
            "variables": variables
        }
        
        # Fazer requisição
        print(f"📤 Publicando: {title} → {wiki_path}")
        response = requests.post(
            f"{WIKI_URL}/graphql",
            json=payload,
            headers=get_graphql_headers(),
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Erro HTTP {response.status_code}: {response.text[:200]}")
            return False
        
        result = response.json()
        
        # Verificar se há erros GraphQL
        if "errors" in result:
            print(f"❌ Erro GraphQL: {result['errors'][0].get('message', 'Unknown')}")
            return False
        
        # Sucesso
        page_data = result.get("data", {}).get("pages", {}).get("create", {})
        print(f"✅ Publicado: {page_data.get('path')} (ID: {page_data.get('id')})")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao publicar: {e}")
        return False

def main():
    """Publicar documentação"""
    docs = [
        (
            "/workspace/eddie-auto-dev/docs/OPERATIONAL_STATUS_2026-04-13.md",
            "system-operations/status-2026-04-13",
            "Status Operacional — 13 de abril de 2026"
        ),
        (
            "/workspace/eddie-auto-dev/docs/LESSONS_LEARNED_2026-04-13.md",
            "knowledge/lessons-learned-2026-04-13",
            "Lições Aprendidas — VPN, OIDC, Containers (2026-04-13)"
        ),
    ]
    
    print("=" * 60)
    print("Publicador de Documentação → Wiki.js")
    print("=" * 60)
    print(f"Wiki URL: {WIKI_URL}")
    print(f"API Key configurada: {'Sim' if WIKI_API_KEY else 'Não (modo anônimo)'}")
    print()
    
    success_count = 0
    for doc_path, wiki_path, title in docs:
        if publish_doc(doc_path, wiki_path, title):
            success_count += 1
        print()
    
    print("=" * 60)
    print(f"Resultado: {success_count}/{len(docs)} documentos publicados")
    print("=" * 60)
    
    return 0 if success_count == len(docs) else 1

if __name__ == "__main__":
    sys.exit(main())
