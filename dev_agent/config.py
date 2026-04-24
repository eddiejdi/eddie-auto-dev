"""
Configuracoes do Dev Agent
"""
from __future__ import annotations
import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_FALLBACK_MODEL = "deepseek-coder:6.7b"
DOCKER_HOST = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")

# Project storage
PROJECTS_DIR = os.getenv("DEV_AGENT_PROJECTS_DIR", "dev_projects")
TRAINING_DIR = os.getenv("DEV_AGENT_TRAINING_DIR", "agent_training")

# Docker settings
DEV_NETWORK = "dev_agent_network"
PYTHON_IMAGE = "python:3.11-slim"
PYTHON_INSTALL_CMD = "pip install --no-cache-dir"
PYTHON_RUN_CMD = "python"
CHROME_IMAGE = "selenium/standalone-chrome:latest"
CHROME_INSTALL_CMD = "pip install selenium webdriver-manager"
STREAMLIT_INSTALL_CMD = "pip install streamlit"
STREAMLIT_RUN_CMD = "streamlit run"
SQL_INSTALL_CMD = "pip install sqlalchemy psycopg2-binary pymysql"
FASTAPI_INSTALL_CMD = "pip install fastapi uvicorn"
FASTAPI_RUN_CMD = "uvicorn main:app --host 0.0.0.0"
FLASK_INSTALL_CMD = "pip install flask"
FLASK_RUN_CMD = "flask run --host=0.0.0.0"

# RAG / Knowledge base
CHROMADB_COLLECTION = "chromadb"
KNOWLEDGE_COLLECTION = "dev_agent_knowledge"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# External frameworks (for project templates)
EXTRA_FRAMEWORKS = ["django", "djangorestframework", "scrapy", "scrapy-splash"]

# System prompts
CODER_PROMPT = (
    "Voce e um programador expert em Python, Selenium, Streamlit, SQL e outras tecnologias.\n"
    "Seu trabalho e criar codigo limpo, testavel e funcional. Sempre inclua tratamento de erros, "
    "documentacao e type hints.\nResponda APENAS com codigo, sem explicacoes extras."
)
DEBUGGER_PROMPT = (
    "Voce e um debugger expert. Analise o erro e sugira correcoes. "
    "Forneca causa raiz, codigo corrigido e explicacao breve."
)
ARCHITECT_PROMPT = (
    "Voce e um arquiteto de software expert. "
    "Projete solucoes escalaveis e bem estruturadas."
)
TESTER_PROMPT = (
    "Voce e um QA engineer expert. "
    "Crie testes abrangentes que cubram casos de sucesso, erro e edge cases."
)
