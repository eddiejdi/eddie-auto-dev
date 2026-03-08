
import requests
import hashlib
from datetime import datetime
from pathlib import Path

def index_file_to_rag(file_path, rag_api_url):
    path = Path(file_path)
    if not path.exists():
        print(f"Arquivo {file_path} não encontrado.")
        return

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    doc_id = hashlib.md5(f"{path.name}".encode()).hexdigest()[:12]
    
    metadata = {
        "source": path.name,
        "title": "Melhores Práticas de Gestão de Projetos e Incidentes",
        "type": "documentation",
        "timestamp": datetime.now().isoformat(),
        "topic": "management"
    }

    # Endpoints comuns
    endpoints = [
        f"{rag_api_url}/api/v1/rag/index",
        f"{rag_api_url}/api/v1/documents",
        f"{rag_api_url}/documents"
    ]

    payload = {
        "documents": [{
            "id": doc_id,
            "content": content,
            "metadata": metadata
        }],
        "collection": "system_documentation"
    }

    success = False
    for endpoint in endpoints:
        try:
            print(f"Tentando endpoint: {endpoint}")
            # Alguns endpoints esperam uma lista de documentos, outros um único documento
            if "index" in endpoint:
                response = requests.post(endpoint, json=payload, timeout=10)
            else:
                # Payload para endpoints que esperam um único documento (como no web_search.py)
                single_payload = {
                    "id": doc_id,
                    "content": content,
                    "text": content,
                    "metadata": metadata,
                    "source": path.name
                }
                response = requests.post(endpoint, json=single_payload, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"Sucesso ao indexar via {endpoint}: {response.text}")
                success = True
                break
            else:
                print(f"Falha em {endpoint}: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Erro ao conectar em {endpoint}: {e}")

    if not success:
        print("Não foi possível indexar via API. Verifique se o serviço RAG está rodando.")

if __name__ == "__main__":
    import os
    RAG_URL = os.environ.get('RAG_API') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:8001"
    FILE = "PROJECT_MANAGEMENT_ITIL_BEST_PRACTICES.md"
    index_file_to_rag(FILE, RAG_URL)
