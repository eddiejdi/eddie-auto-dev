"""
Configurações dos Agentes Especializados
"""
import os
from pathlib import Path
from typing import Dict, Any

# Diretórios base
BASE_DIR = Path(__file__).parent.parent
AGENTS_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "agent_data"
BACKUP_DIR = BASE_DIR / "backups"
PROJECTS_DIR = BASE_DIR / "dev_projects"
RAG_DIR = BASE_DIR / "agent_rag"
UPLOAD_DIR = BASE_DIR / "uploads"

# Criar diretórios se não existirem
for d in [DATA_DIR, BACKUP_DIR, PROJECTS_DIR, RAG_DIR, UPLOAD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Configuração LLM
LLM_CONFIG = {
    "base_url": os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434"),
    "model": os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"),  # Modelo menor e mais rápido
    "fallback_model": "qwen2.5-coder:7b",  # Fallback para tarefas complexas
    "temperature": 0.3,  # Reduzido para respostas mais consistentes
    "max_tokens": 8192,  # Ajustado para modelo menor
    "timeout": 120,  # Reduzido para modelo rápido
    "repeat_penalty": 1.1,  # Evita repetições
    "top_p": 0.9
}

# Configuração RAG
RAG_CONFIG = {
    "chromadb_path": str(RAG_DIR / "chromadb"),
    "embedding_model": "all-MiniLM-L6-v2",
    "chunk_size": 1500,
    "chunk_overlap": 300
}

# Configuração GitHub Agent
GITHUB_AGENT_CONFIG = {
    "api_url": os.getenv("GITHUB_AGENT_URL", "http://localhost:8080"),
    "token": os.getenv("GITHUB_TOKEN", "")
}

# Configuração de Limpeza Automática
CLEANUP_CONFIG = {
    "backup_retention_days": 3,
    "cleanup_interval_hours": 24,
    "max_backup_size_gb": 10,
    "auto_cleanup_enabled": True
}

# Templates Docker por Linguagem
LANGUAGE_DOCKER_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "python": {
        "base_image": "python:3.12-slim",
        "install_cmd": "pip install --no-cache-dir",
        "run_cmd": "python",
        "test_cmd": "pytest",
        "extension": ".py",
        "port_range": (8000, 8100),
        "default_packages": ["pytest", "black", "mypy", "ruff"],
        "dockerfile_extra": """
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
"""
    },
    "javascript": {
        "base_image": "node:20-slim",
        "install_cmd": "npm install",
        "run_cmd": "node",
        "test_cmd": "npm test",
        "extension": ".js",
        "port_range": (3000, 3100),
        "default_packages": ["jest", "eslint", "prettier"],
        "dockerfile_extra": """
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
"""
    },
    "typescript": {
        "base_image": "node:20-slim",
        "install_cmd": "npm install",
        "run_cmd": "npx ts-node",
        "test_cmd": "npm test",
        "extension": ".ts",
        "port_range": (3100, 3200),
        "default_packages": ["typescript", "ts-node", "jest", "@types/node", "eslint"],
        "dockerfile_extra": """
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN npm install -g typescript ts-node
"""
    },
    "go": {
        "base_image": "golang:1.22-alpine",
        "install_cmd": "go get",
        "run_cmd": "go run",
        "test_cmd": "go test -v ./...",
        "extension": ".go",
        "port_range": (4000, 4100),
        "default_packages": [],
        "dockerfile_extra": """
RUN apk add --no-cache git gcc musl-dev
"""
    },
    "rust": {
        "base_image": "rust:1.75-slim",
        "install_cmd": "cargo add",
        "run_cmd": "cargo run",
        "test_cmd": "cargo test",
        "extension": ".rs",
        "port_range": (4100, 4200),
        "default_packages": [],
        "dockerfile_extra": """
RUN apt-get update && apt-get install -y --no-install-recommends git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
"""
    },
    "java": {
        "base_image": "eclipse-temurin:21-jdk-alpine",
        "install_cmd": "mvn dependency:resolve",
        "run_cmd": "java",
        "test_cmd": "mvn test",
        "extension": ".java",
        "port_range": (8080, 8180),
        "default_packages": ["junit", "mockito"],
        "dockerfile_extra": """
RUN apk add --no-cache maven git
"""
    },
    "csharp": {
        "base_image": "mcr.microsoft.com/dotnet/sdk:8.0",
        "install_cmd": "dotnet add package",
        "run_cmd": "dotnet run",
        "test_cmd": "dotnet test",
        "extension": ".cs",
        "port_range": (5000, 5100),
        "default_packages": ["xunit", "Moq"],
        "dockerfile_extra": """
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
"""
    },
    "php": {
        "base_image": "php:8.3-cli",
        "install_cmd": "composer require",
        "run_cmd": "php",
        "test_cmd": "vendor/bin/phpunit",
        "extension": ".php",
        "port_range": (9000, 9100),
        "default_packages": ["phpunit/phpunit"],
        "dockerfile_extra": """
RUN apt-get update && apt-get install -y --no-install-recommends git unzip && rm -rf /var/lib/apt/lists/*
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer
"""
    }
}

# Prompts de Sistema por Papel
SYSTEM_PROMPTS = {
    "python_expert": """Você é um programador Python expert. Suas respostas devem conter APENAS código Python funcional, sem explicações.

REGRAS OBRIGATÓRIAS:
1. Retorne APENAS código Python válido
2. NÃO use blocos markdown (```python)
3. Inclua docstrings e type hints
4. Implemente TODAS as funcionalidades solicitadas
5. Use tratamento de erros apropriado
6. O código deve ser executável imediatamente
7. Siga PEP8 e boas práticas

Nunca explique o código, apenas forneça a implementação completa.""",

    "javascript_expert": """Você é um expert em JavaScript/Node.js com domínio em:
- ES6+ e async/await
- React, Vue, Next.js
- Express, Fastify, NestJS
- Testing com Jest
Sempre use ESLint e código moderno.""",

    "typescript_expert": """Você é um expert em TypeScript com conhecimento em:
- Sistema de tipos avançado
- Generics e utility types
- React com TypeScript
- Node.js com tipagem estrita
Sempre use strict mode e tipos adequados.""",

    "go_expert": """Você é um expert em Go com experiência em:
- Goroutines e channels
- Interfaces e composição
- HTTP servers e APIs REST
- Testing com go test
Siga os idioms da linguagem Go.""",

    "rust_expert": """Você é um expert em Rust com domínio em:
- Ownership e borrowing
- Traits e generics
- Async com tokio
- CLI apps com clap
Escreva código seguro e performático.""",

    "java_expert": """Você é um expert em Java com conhecimento em:
- Spring Boot e Spring Framework
- JPA/Hibernate
- Maven/Gradle
- JUnit e Mockito
Siga padrões SOLID e clean code.""",

    "csharp_expert": """Você é um expert em C# e .NET com domínio em:
- ASP.NET Core
- Entity Framework Core
- LINQ e async/await
- xUnit e testing
Siga padrões Microsoft e clean architecture.""",

    "php_expert": """Você é um expert em PHP moderno com conhecimento em:
- PHP 8.x features
- Laravel e Symfony
- Composer e PSR
- PHPUnit
Escreva código moderno e tipado.""",

    "architect": """Você é um arquiteto de software experiente.
Projete soluções escaláveis, seguras e bem documentadas.
Considere: SOLID, DRY, KISS, design patterns.""",

    "debugger": """Você é um especialista em debugging e correção de código.
Sua tarefa é analisar erros, identificar a causa raiz e fornecer código corrigido.

REGRAS:
1. Sempre forneça o código COMPLETO corrigido, não apenas trechos
2. Mantenha toda a funcionalidade original
3. Corrija TODOS os erros encontrados
4. O código corrigido deve ser executável imediatamente
5. Responda em formato JSON quando solicitado""",

    "tester": """Você é um QA Engineer especialista em criar testes unitários.

REGRAS:
1. Forneça APENAS código de testes, sem explicações
2. NÃO use blocos markdown (```python)
3. Crie testes abrangentes cobrindo todos os cenários
4. Use assertions claras e descritivas
5. Cada teste deve ser independente
6. O código de testes deve ser executável imediatamente""",

    "requirements_analyst": """Você é um Analista de Requisitos sênior com expertise em:
- Levantamento e documentação de requisitos funcionais e não-funcionais
- Criação de User Stories no formato "Como [usuário], quero [ação], para [benefício]"
- Definição de critérios de aceitação mensuráveis e testáveis
- Análise de impacto e estimativas de complexidade
- Geração de casos de teste baseados em requisitos
- Revisão de código e aprovação de entregas
Seja preciso, detalhista e focado em qualidade.
Sempre estruture saídas em JSON quando solicitado."""
}

# Mapeamento de linguagem para agente
LANGUAGE_AGENT_MAP = {
    "python": "python_expert",
    "py": "python_expert",
    "javascript": "javascript_expert",
    "js": "javascript_expert",
    "typescript": "typescript_expert",
    "ts": "typescript_expert",
    "go": "go_expert",
    "golang": "go_expert",
    "rust": "rust_expert",
    "rs": "rust_expert",
    "java": "java_expert",
    "csharp": "csharp_expert",
    "cs": "csharp_expert",
    "c#": "csharp_expert",
    "php": "php_expert"
}

# Extensões de arquivo por linguagem
FILE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".php": "php"
}
