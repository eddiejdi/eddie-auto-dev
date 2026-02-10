# 📡 API Reference - Eddie Auto-Dev System

## Base URL

http://localhost:8503
## Autenticação

A API atualmente não requer autenticação. Em produção, recomenda-se adicionar tokens de API.

---

## Endpoints

### Health & Status

#### GET /health
Verifica se a API está funcionando.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-09T18:00:00.000000"
}
#### GET /status
Retorna status completo do sistema.

**Response:**
```json
{
  "ollama": {
    "connected": true,
    "model": "eddie-coder",
    "host": "http://192.168.15.2:11434"
  },
  "docker": {
    "available": true,
    "containers": 3,
    "images": 8
  },
  "rag": {
    "collections": ["python_code", "python_docs", "javascript_code"],
    "total_documents": 1542
  },
  "agents": {
    "active": ["python", "javascript"],
    "available": ["python", "javascript", "typescript", "go", "rust", "java", "csharp", "php"]
  }
}
---

### Agentes

#### GET /agents
Lista todos os agentes disponíveis.

**Response:**
```json
{
  "available_languages": [
    "python",
    "javascript",
    "typescript",
    "go",
    "rust",
    "java",
    "csharp",
    "php"
  ],
  "active_agents": [
    {
      "language": "python",
      "name": "Python Expert Agent",
      "status": "active"
    }
  ]
}
#### GET /agents/{language}
Obtém informações de um agente específico.

**Parameters:**
- `language` (path): Linguagem do agente

**Response:**
```json
{
  "name": "Python Expert Agent",
  "language": "python",
  "capabilities": [
    "code_generation",
    "testing",
    "debugging",
    "documentation"
  ],
  "status": {
    "active": true,
    "container_running": true,
    "last_used": "2026-01-09T17:45:00.000000"
  }
}
#### POST /agents/{language}/activate
Ativa um agente específico.

**Parameters:**
- `language` (path): Linguagem do agente

**Response:**
```json
{
  "message": "Agente Python Expert Agent ativado",
  "agent": {
    "name": "Python Expert Agent",
    "language": "python",
    "active": true
  }
}
---

### Projetos

#### POST /projects/create
Cria um novo projeto.

**Request Body:**
```json
{
  "language": "python",
  "description": "API REST para gerenciamento de tarefas com FastAPI",
  "project_name": "task-api"
}
**Response:**
```json
{
  "success": true,
  "project_name": "task-api",
  "project_path": "/home/homelab/myClaude/projects/python/task-api",
  "language": "python",
  "files_created": [
    "main.py",
    "requirements.txt",
    "README.md",
    "tests/test_main.py",
    "Dockerfile",
    ".gitignore"
  ],
  "container_id": "abc123def456"
}
#### GET /projects/{language}
Lista projetos de uma linguagem.

**Parameters:**
- `language` (path): Linguagem dos projetos

**Response:**
```json
{
  "projects": [
    {
      "name": "task-api",
      "path": "/home/homelab/myClaude/projects/python/task-api",
      "language": "python",
      "created_at": "2026-01-09T15:30:00.000000",
      "last_modified": "2026-01-09T17:45:00.000000"
    },
    {
      "name": "calculator",
      "path": "/home/homelab/myClaude/projects/python/calculator",
      "language": "python",
      "created_at": "2026-01-08T10:00:00.000000",
      "last_modified": "2026-01-08T12:30:00.000000"
    }
  ]
}
#### GET /projects/{language}/{project_name}/download
Baixa um projeto como arquivo ZIP.

**Parameters:**
- `language` (path): Linguagem do projeto
- `project_name` (path): Nome do projeto

**Response:**
- Content-Type: `application/zip`
- Body: Arquivo ZIP binário

---

### Código

#### POST /code/generate
Gera código baseado em descrição.

**Request Body:**
```json
{
  "language": "python",
  "description": "Função que calcula o fatorial de um número usando recursão",
  "context": "Deve incluir tratamento de erros para números negativos"
}
**Response:**
```json
{
  "success": true,
  "code": "def factorial(n: int) -> int:\n    \"\"\"Calcula o fatorial de n usando recursão.\"\"\"\n    if n < 0:\n        raise ValueError(\"Número não pode ser negativo\")\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
  "language": "python",
  "explanation": "A função utiliza recursão para calcular o fatorial. Inclui validação para números negativos.",
  "tests_generated": "def test_factorial():\n    assert factorial(5) == 120\n    assert factorial(0) == 1"
}
#### POST /code/execute
Executa código em ambiente isolado.

**Request Body:**
```json
{
  "language": "python",
  "code": "print('Hello, World!')\nfor i in range(5):\n    print(f'Número: {i}')",
  "run_tests": false
}
**Response:**
```json
{
  "success": true,
  "output": "Hello, World!\nNúmero: 0\nNúmero: 1\nNúmero: 2\nNúmero: 3\nNúmero: 4",
  "execution_time": 0.045,
  "container_id": "xyz789abc123"
}
#### POST /code/analyze-error
Analisa um erro de código e sugere correção.

**Request Body:**
```json
{
  "language": "python",
  "code": "def divide(a, b):\n    return a / b\n\nresult = divide(10, 0)",
  "error_message": "ZeroDivisionError: division by zero"
}
**Response:**
```json
{
  "success": true,
  "analysis": "O erro ocorre porque você está tentando dividir por zero na função divide().",
  "suggestion": "Adicione uma verificação para evitar divisão por zero.",
  "corrected_code": "def divide(a, b):\n    if b == 0:\n        raise ValueError(\"Divisor não pode ser zero\")\n    return a / b\n\ntry:\n    result = divide(10, 0)\nexcept ValueError as e:\n    print(f\"Erro: {e}\")"
}
---

### RAG (Retrieval Augmented Generation)

#### POST /rag/search
Busca no banco de conhecimento.

**Request Body:**
```json
{
  "query": "como criar endpoints REST com FastAPI",
  "language": "python",
  "n_results": 5
}
**Response:**
```json
{
  "success": true,
  "results": [
    {
      "id": "doc_123",
      "content": "@app.get('/items/{item_id}')\nasync def read_item(item_id: int):\n    return {'item_id': item_id}",
      "metadata": {
        "language": "python",
        "type": "code",
        "title": "FastAPI endpoint example"
      },
      "score": 0.92
    },
    {
      "id": "doc_456",
      "content": "FastAPI é um framework moderno para criar APIs...",
      "metadata": {
        "language": "python",
        "type": "documentation"
      },
      "score": 0.87
    }
  ],
  "total_found": 2
}
#### POST /rag/index
Indexa novo conteúdo no RAG.

**Request Body:**
```json
{
  "content": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'message': 'Hello World'}",
  "language": "python",
  "content_type": "code",
  "title": "FastAPI Hello World",
  "description": "Exemplo básico de aplicação FastAPI"
}
**Response:**
```json
{
  "success": true,
  "id": "doc_789",
  "collection": "python_code",
  "message": "Conteúdo indexado com sucesso"
}
#### POST /rag/index-file
Indexa arquivo no RAG.

**Request Body (multipart/form-data):**
- `file`: Arquivo a ser indexado
- `language`: Linguagem do conteúdo
- `content_type`: Tipo (code, documentation)

**Response:**
```json
{
  "success": true,
  "id": "doc_101",
  "filename": "example.py",
  "lines_indexed": 150
}
---

### Docker

#### GET /docker/containers
Lista containers dos agentes.

**Response:**
```json
{
  "containers": [
    {
      "id": "abc123",
      "name": "python-agent-task-api",
      "image": "python:3.12-slim",
      "status": "running",
      "ports": {"8000/tcp": "8000"},
      "created": "2026-01-09T15:30:00.000000"
    }
  ]
}
#### POST /docker/containers/{id}/start
Inicia um container.

**Parameters:**
- `id` (path): ID do container

**Response:**
```json
{
  "success": true,
  "container_id": "abc123",
  "status": "running"
}
#### POST /docker/containers/{id}/stop
Para um container.

**Parameters:**
- `id` (path): ID do container

**Response:**
```json
{
  "success": true,
  "container_id": "abc123",
  "status": "stopped"
}
#### DELETE /docker/containers/{id}
Remove um container.

**Parameters:**
- `id` (path): ID do container

**Response:**
```json
{
  "success": true,
  "message": "Container abc123 removido"
}
#### POST /docker/exec
Executa comando em container.

**Request Body:**
```json
{
  "container_id": "abc123",
  "command": "python --version",
  "timeout": 30
}
**Response:**
```json
{
  "success": true,
  "output": "Python 3.12.1",
  "exit_code": 0,
  "execution_time": 0.12
}
---

### GitHub

#### POST /github/push
Push de projeto para GitHub.

**Request Body:**
```json
{
  "language": "python",
  "project_name": "task-api",
  "repo_name": "task-api",
  "description": "API REST para gerenciamento de tarefas"
}
**Response:**
```json
{
  "success": true,
  "repo_url": "https://github.com/eddiejdi/task-api",
  "branch": "main",
  "commit_sha": "a1b2c3d4e5f6",
  "files_pushed": 6
}
#### GET /github/repos
Lista repositórios do usuário.

**Response:**
```json
{
  "repos": [
    {
      "name": "task-api",
      "full_name": "eddiejdi/task-api",
      "url": "https://github.com/eddiejdi/task-api",
      "description": "API REST para gerenciamento de tarefas",
      "created_at": "2026-01-09T15:30:00Z",
      "updated_at": "2026-01-09T17:45:00Z"
    }
  ]
}
---

### Cleanup

#### POST /cleanup/run
Executa limpeza de recursos.

**Response:**
```json
{
  "success": true,
  "report": {
    "containers_removed": 2,
    "images_removed": 0,
    "projects_archived": 1,
    "space_freed_mb": 150.5
  }
}
#### GET /cleanup/storage
Retorna status de armazenamento.

**Response:**
```json
{
  "total_gb": 100.0,
  "used_gb": 45.2,
  "available_gb": 54.8,
  "usage_percent": 45.2,
  "by_category": {
    "projects": "12.5 GB",
    "containers": "8.3 GB",
    "images": "15.2 GB",
    "rag_db": "2.1 GB",
    "backups": "7.1 GB"
  }
}
#### GET /cleanup/backups
Lista backups disponíveis.

**Response:**
```json
{
  "backups": [
    {
      "path": "/home/homelab/backups/2026-01-09",
      "date": "2026-01-09",
      "size_mb": 250.5
    },
    {
      "path": "/home/homelab/backups/2026-01-08",
      "date": "2026-01-08",
      "size_mb": 248.2
    }
  ]
}
---

## Códigos de Erro

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso |
| 400 | Requisição inválida |
| 404 | Recurso não encontrado |
| 500 | Erro interno do servidor |
| 503 | Serviço indisponível (Ollama offline, etc.) |

### Exemplo de Erro

```json
{
  "detail": "Linguagem não suportada: cobol",
  "error_code": "UNSUPPORTED_LANGUAGE",
  "timestamp": "2026-01-09T18:00:00.000000"
}
---

## Rate Limiting

Atualmente não há rate limiting implementado. Para uso em produção, recomenda-se:

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/resource")
@limiter.limit("60/minute")
async def get_resource():
    ...
---

## Exemplos de Uso

### Python (httpx)

import httpx
import asyncio

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8503") as client:
        # Health check
        r = await client.get("/health")
        print(r.json())
        
        # Criar projeto
        r = await client.post("/projects/create", json={
            "language": "python",
            "description": "Hello World API"
        })
        print(r.json())

asyncio.run(main())
### cURL

```bash
# Health
curl http://localhost:8503/health

# Criar projeto
curl -X POST http://localhost:8503/projects/create \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "description": "API de exemplo"}'

# Buscar RAG
curl -X POST http://localhost:8503/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "FastAPI", "language": "python"}'
### JavaScript (fetch)

```javascript
// Health check
const health = await fetch('http://localhost:8503/health')
  .then(r => r.json());

// Criar projeto
const project = await fetch('http://localhost:8503/projects/create', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    language: 'javascript',
    description: 'Node.js Express API'
  })
}).then(r => r.json());
