#!/usr/bin/env python3
"""Script para indexar documentacao do homelab no RAG."""

import requests
import json

RAG_API = "http://localhost:8001"

docs = []

# Ler README do homelab-scripts
readme_path = "/home/homelab/projects/homelab-scripts/README.md"
with open(readme_path, "r") as f:
    content = f.read()
    docs.append({
        "id": "homelab-infrastructure-docs",
        "content": content,
        "metadata": {
            "source": readme_path,
            "doc_type": "documentation",
            "project_id": "homelab",
            "tags": ["homelab", "infrastructure", "services", "urls"]
        }
    })

# Ler README do github-agent
readme_path = "/home/homelab/projects/github-agent/README.md"
with open(readme_path, "r") as f:
    content = f.read()
    docs.append({
        "id": "github-agent-docs",
        "content": content,
        "metadata": {
            "source": readme_path,
            "doc_type": "documentation",
            "project_id": "github-agent",
            "tags": ["github", "agent", "llm", "streamlit"]
        }
    })

# Ler README do rag-dashboard
readme_path = "/home/homelab/projects/rag-dashboard/README.md"
with open(readme_path, "r") as f:
    content = f.read()
    docs.append({
        "id": "rag-dashboard-docs",
        "content": content,
        "metadata": {
            "source": readme_path,
            "doc_type": "documentation",
            "project_id": "rag-dashboard",
            "tags": ["rag", "dashboard", "monitoring", "streamlit"]
        }
    })

# Indexar guia ESM local do repo
esm_path = "/home/edenilson/eddie-auto-dev/docs/ESM_ACTIVATION_HOMELAB.md"
with open(esm_path, "r") as f:
    content = f.read()
    docs.append({
        "id": "esm-activation-guide",
        "content": content,
        "metadata": {
            "source": esm_path,
            "doc_type": "documentation",
            "project_id": "eddie-auto-dev",
            "tags": ["esm", "ubuntu pro", "homelab"]
        }
    })

# Indexar README do script ESM
script_readme = "/home/edenilson/eddie-auto-dev/scripts/README-enable_esm.md"
with open(script_readme, "r") as f:
    content = f.read()
    docs.append({
        "id": "esm-script-readme",
        "content": content,
        "metadata": {
            "source": script_readme,
            "doc_type": "documentation",
            "project_id": "eddie-auto-dev",
            "tags": ["esm", "script", "homelab"]
        }
    })

# Fly.io tunnel indexing removed — flyio-tunnel artifacts deprecated/removed.

# Enviar para indexacao
payload = {
    "documents": docs,
    "collection": "homelab"
}

print(f"Indexando {len(docs)} documentos...")
response = requests.post(f"{RAG_API}/api/v1/rag/index", json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
