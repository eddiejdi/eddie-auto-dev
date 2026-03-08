#!/usr/bin/env python3
"""
Script simplificado para atualizar RAG usando Ollama embeddings
"""

import os
import json
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import chromadb

# Configurações
BASE_DIR = Path(__file__).parent
TRAINING_DIR = BASE_DIR / "training_data"
CHROMA_DIR = BASE_DIR / "chroma_db"
DOCS_DIR = BASE_DIR / "docs"
OLLAMA_URL = os.environ.get('OLLAMA_URL', f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434")

# Conhecimento da sessão atual
KNOWLEDGE = [
    {
        "id": "integration_openwebui",
        "topic": "Integração Open WebUI + Telegram + WhatsApp",
        "content": """Integração entre modelos Ollama, Open WebUI e bots.
        Open WebUI: http://${HOMELAB_HOST}:3000
        Ollama: http://${HOMELAB_HOST}:11434
        WAHA: http://${HOMELAB_HOST}:3001
        Módulo: openwebui_integration.py com perfis automáticos."""
    },
    {
        "id": "models_uncensored",
        "topic": "Modelos sem Censura",
        "content": """shared-assistant baseado em dolphin-llama3:8b - sem censura.
        shared-coder baseado em qwen2.5-coder:7b - apenas código.
        Usar dolphin para assistente pessoal completo."""
    },
    {
        "id": "waha_whatsapp",
        "topic": "WAHA WhatsApp API",
        "content": """Docker: docker run -d --name waha -p 3001:3000 -e WAHA_NO_API_KEY=True devlikeapro/waha:latest
        Dashboard: http://${HOMELAB_HOST}:3001/dashboard
        Usar engine WEBJS para QR code estável."""
    },
    {
        "id": "model_profiles",
        "topic": "Perfis de Modelo",
        "content": """Perfis: assistant (pessoal), coder (código), homelab (infra), fast (1.5b), advanced (16b).
        Auto-seleção por palavras-chave no prompt.
        Comandos Telegram: /models, /profiles, /profile, /use"""
    },
    {
        "id": "ollama_commands",
        "topic": "Comandos Ollama",
        "content": """ollama list - listar modelos
        ollama create nome -f Modelfile - criar modelo
        ollama run modelo - testar modelo
        ollama show modelo - ver info"""
    }
]

def get_ollama_embedding(text: str) -> List[float]:
    """Gera embedding usando Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()["embedding"]
    except Exception as e:
        print(f"⚠️ Erro embedding: {e}")
    return None

def index_to_chromadb():
    """Indexa no ChromaDB usando Ollama embeddings"""
    print("📚 Conectando ao ChromaDB...")
    
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    # Criar coleção sem embedding function (vamos fornecer manualmente)
    try:
        collection = client.get_collection("shared_knowledge_v2")
        print(f"📊 Coleção existente: {collection.count()} docs")
    except:
        collection = client.create_collection(
            name="shared_knowledge_v2",
            metadata={"hnsw:space": "cosine"}
        )
        print("📊 Nova coleção criada")
    
    added = 0
    for item in KNOWLEDGE:
        print(f"  → Processando: {item['topic'][:40]}...")
        
        # Gerar embedding
        text = f"{item['topic']}\n{item['content']}"
        embedding = get_ollama_embedding(text)
        
        if embedding:
            collection.upsert(
                ids=[item["id"]],
                documents=[text],
                embeddings=[embedding],
                metadatas=[{"topic": item["topic"], "date": datetime.now().isoformat()}]
            )
            added += 1
    
    print(f"✅ Adicionados {added} documentos. Total: {collection.count()}")
    return collection.count()

def save_training_jsonl():
    """Salva dados de treinamento"""
    pairs = [
            ("Como integrar Open WebUI com Telegram?", "Use openwebui_integration.py que conecta ao Ollama (${HOMELAB_HOST}:11434) com seleção automática de modelo."),
        ("Qual modelo usar para assistente pessoal?", "Use shared-assistant baseado em dolphin-llama3:8b, sem censura para uso pessoal."),
        ("Como configurar WAHA para WhatsApp?", "docker run -d --name waha -p 3001:3000 -e WAHA_NO_API_KEY=True devlikeapro/waha:latest. Dashboard em :3001/dashboard"),
        ("Como criar modelo restrito para código?", "Use Modelfile com SYSTEM prompt restritivo. Exemplo: shared-coder-strict.Modelfile"),
        ("Quais comandos do Telegram bot?", "/models (lista), /profiles (perfis), /profile <nome>, /use <modelo>, /auto_profile"),
        ("O QR Code do WhatsApp expira rápido?", "Use engine WEBJS: -e WHATSAPP_DEFAULT_ENGINE=WEBJS. Mais estável que NOWEB."),
        ("Diferença shared-assistant e shared-coder?", "shared-assistant (dolphin) sem censura para uso pessoal. shared-coder (qwen) restrito a código."),
        ("Onde ficam os serviços?", "Ollama: ${HOMELAB_HOST}:11434, Open WebUI: :3000, WAHA: :3001, Streamlit: localhost:8502"),
    ]
    
    filename = TRAINING_DIR / f"training_{datetime.now().strftime('%Y-%m-%d')}_knowledge.jsonl"
    with open(filename, "w") as f:
        for q, a in pairs:
            f.write(json.dumps({"prompt": q, "completion": a}, ensure_ascii=False) + "\n")
    
    print(f"✅ Treino salvo: {filename} ({len(pairs)} pares)")
    return filename

def main():
    print("🚀 Atualizando RAG e Treinamento...")
    print("=" * 50)
    
    # 1. Salvar treino
    print("\n📝 Salvando dados de treinamento...")
    save_training_jsonl()
    
    # 2. Indexar RAG
    print("\n🔍 Indexando no ChromaDB...")
    index_to_chromadb()
    
    print("\n✅ Concluído!")

if __name__ == "__main__":
    main()
