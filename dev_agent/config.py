"""
Configuracoes do Dev Agent
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent
PROJECTS_DIR = BASE_DIR / "dev_projects"
TRAINING_DIR = BASE_DIR / "agent_training"

LLM_CONFIG = {
    "base_url": os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434"),
    "model": os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
    "fallback_model": "deepseek-coder:6.7b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "timeout": 120
}

DOCKER_CONFIG = {
    "host": os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock"),
    "network_name": "dev_agent_network",
    "default_timeout": 300,
    "max_retries": 5
}

DOCKER_TEMPLATES = {
    "python": {"base_image": "python:3.11-slim", "install_cmd": "pip install --no-cache-dir", "run_cmd": "python"},
    "selenium": {"base_image": "selenium/standalone-chrome:latest", "install_cmd": "pip install selenium webdriver-manager", "run_cmd": "python"},
    "streamlit": {"base_image": "python:3.11-slim", "install_cmd": "pip install streamlit", "run_cmd": "streamlit run", "port": 8501},
    "sql": {"base_image": "python:3.11-slim", "install_cmd": "pip install sqlalchemy psycopg2-binary pymysql", "run_cmd": "python"},
    "fastapi": {"base_image": "python:3.11-slim", "install_cmd": "pip install fastapi uvicorn", "run_cmd": "uvicorn main:app --host 0.0.0.0", "port": 8000},
    "flask": {"base_image": "python:3.11-slim", "install_cmd": "pip install flask", "run_cmd": "flask run --host=0.0.0.0", "port": 5000}
}

TEST_CONFIG = {"max_iterations": 10, "test_timeout": 60, "auto_fix": True, "verbose": True}

RAG_CONFIG = {
    "chromadb_path": str(TRAINING_DIR / "chromadb"),
    "collection_name": "dev_agent_knowledge",
    "embedding_model": "all-MiniLM-L6-v2",
    "chunk_size": 1000,
    "chunk_overlap": 200
}

SUPPORTED_TECHNOLOGIES = {
    "python": ["pytest", "black", "flake8", "mypy"],
    "selenium": ["selenium", "webdriver-manager", "pytest-selenium"],
    "streamlit": ["streamlit", "pandas", "plotly"],
    "sql": ["sqlalchemy", "alembic", "psycopg2-binary", "pymysql"],
    "fastapi": ["fastapi", "uvicorn", "pydantic", "httpx"],
    "flask": ["flask", "flask-cors", "flask-sqlalchemy"],
    "django": ["django", "djangorestframework"],
    "scrapy": ["scrapy", "scrapy-splash"],
    "pandas": ["pandas", "numpy", "openpyxl"],
    "machine_learning": ["scikit-learn", "tensorflow", "torch"]
}

SYSTEM_PROMPTS = {
    "coder": """Voce e um programador expert em Python, Selenium, Streamlit, SQL e outras tecnologias.
Seu trabalho e criar codigo limpo, testavel e funcional. Sempre inclua tratamento de erros, documentacao e type hints.
Responda APENAS com codigo, sem explicacoes extras.""",
    "debugger": """Voce e um debugger expert. Analise o erro e sugira correcoes. Forneca causa raiz, codigo corrigido e explicacao breve.""",
    "architect": """Voce e um arquiteto de software expert. Projete solucoes escalaveis e bem estruturadas.""",
    "tester": """Voce e um QA engineer expert. Crie testes abrangentes que cubram casos de sucesso, erro e edge cases."""
}
