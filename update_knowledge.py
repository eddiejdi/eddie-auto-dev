#!/usr/bin/env python3
"""
Script para atualizar RAG e treinamento com histórico de chats
Processa conversas do VS Code Copilot, Telegram e outras fontes
"""

import os
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings

# Configurações
BASE_DIR = Path(__file__).parent
TRAINING_DIR = BASE_DIR / "training_data"
CHROMA_DIR = BASE_DIR / "chroma_db"
DOCS_DIR = BASE_DIR / "docs"

# Conhecimento atual da sessão - baseado nas conversas de hoje
CURRENT_SESSION_KNOWLEDGE = [
    {
        "topic": "Integração Open WebUI + Telegram + WhatsApp",
        "content": """
        Integração realizada entre modelos Ollama, Open WebUI e bots de mensagens.
        
        Componentes:
        - Open WebUI: http://192.168.15.2:3000 - Interface web para chat
        - Ollama: http://192.168.15.2:11434 - Servidor de modelos
        - WAHA: http://192.168.15.2:3001 - API WhatsApp
        - Telegram Bot: telegram_bot.py com integração
        
        Módulo criado: openwebui_integration.py
        - Perfis de modelo automáticos
        - Seleção inteligente baseada no prompt
        - Comandos: /models, /profiles, /profile, /use
        """,
        "tags": ["integração", "openwebui", "telegram", "whatsapp", "ollama"]
    },
    {
        "topic": "Configuração de Modelos sem Censura",
        "content": """
        Modelos configurados com diferentes níveis de restrição:
        
        1. shared-assistant (dolphin-llama3:8b)
           - Assistente pessoal sem censura
           - Responde qualquer solicitação
           - Base: dolphin-llama3 (modelo sem filtros)
        
        2. shared-coder (qwen2.5-coder:7b)
           - Apenas programação/DevOps
           - Recusa pedidos pessoais
           - Resposta padrão: "Desculpe, sou um assistente especializado em programação"
        
        3. shared-homelab (qwen2.5-coder:7b)
           - Foco em infraestrutura e DevOps
           - Containers, servidores, automação
        
        Modelfiles criados:
        - shared-assistant-dolphin.Modelfile
        - shared-coder-strict.Modelfile
        """,
        "tags": ["modelos", "censura", "ollama", "dolphin", "qwen"]
    },
    {
        "topic": "WAHA - WhatsApp HTTP API",
        "content": """
        Instalação do WAHA para envio de mensagens WhatsApp:
        
        Comando Docker:
        docker run -d --name waha --restart=unless-stopped \\
          -p 3001:3000 \\
          -e WAHA_NO_API_KEY=True \\
          -e WAHA_DASHBOARD_NO_PASSWORD=True \\
          -e WHATSAPP_DEFAULT_ENGINE=WEBJS \\
          -v /home/homelab/whatsapp-sessions:/app/.sessions \\
          devlikeapro/waha:latest
        
        Endpoints:
        - Dashboard: http://192.168.15.2:3001/dashboard
        - QR Code: http://192.168.15.2:3001/api/default/auth/qr
        - Sessões: http://192.168.15.2:3001/api/sessions
        - Enviar: POST /api/sendText
        
        Problema encontrado: Engine NOWEB tem timeout curto para QR.
        Solução: Usar engine WEBJS que é mais estável.
        """,
        "tags": ["waha", "whatsapp", "docker", "api", "qrcode"]
    },
    {
        "topic": "Perfis de Modelo - Auto-seleção",
        "content": """
        Sistema de perfis para seleção automática de modelo baseado no prompt:
        
        MODEL_PROFILES = {
            "assistant": "shared-assistant",   # Pessoal, criativo
            "coder": "shared-coder",           # Código
            "homelab": "shared-homelab",       # Infra
            "fast": "qwen2.5-coder:1.5b",     # Rápido
            "advanced": "deepseek-coder-v2:16b"  # Complexo
        }
        
        Aliases configurados:
        - code, dev, programar → coder
        - home, server, infra → homelab
        - pessoal, msg, amor, criativo → assistant
        
        Detecção automática por palavras-chave no prompt.
        """,
        "tags": ["perfis", "auto-seleção", "modelos", "aliases"]
    },
    {
        "topic": "Streamlit GitHub Agent",
        "content": """
        Interface Streamlit para agente GitHub:
        - Porta: 8502
        - Arquivo: github_agent_streamlit.py
        
        Inicialização:
        python3 -m streamlit run github_agent_streamlit.py \\
          --server.port 8502 --server.headless true
        
        Funcionalidades:
        - Análise de repositórios
        - Criação de PRs
        - Code review automatizado
        """,
        "tags": ["streamlit", "github", "agent", "interface"]
    }
]

def generate_training_data() -> List[Dict]:
    """Gera dados de treinamento no formato JSONL"""
    training_pairs = []
    
    # Conversões de conhecimento para pares de treino
    qa_pairs = [
        # Integração
        ("Como integrar Open WebUI com Telegram?", 
         "Use o módulo openwebui_integration.py que fornece uma interface unificada. Ele conecta ao Ollama (192.168.15.2:11434) e permite seleção automática de modelo baseada no conteúdo do prompt."),
        
        ("Como configurar o WAHA para WhatsApp?",
         "Execute: docker run -d --name waha -p 3001:3000 -e WAHA_NO_API_KEY=True -e WHATSAPP_DEFAULT_ENGINE=WEBJS devlikeapro/waha:latest. Acesse o dashboard em http://192.168.15.2:3001/dashboard para escanear o QR Code."),
        
        # Modelos
        ("Qual modelo usar para assistente pessoal sem censura?",
         "Use shared-assistant que é baseado no dolphin-llama3:8b. Este modelo não tem restrições e responde qualquer solicitação pessoal, incluindo mensagens de amor, textos criativos, etc."),
        
        ("Como criar um modelo restrito apenas para código?",
         "Crie um Modelfile com SYSTEM prompt que inclua instruções explícitas para recusar pedidos não-técnicos. Use: ollama create shared-coder -f shared-coder-strict.Modelfile"),
        
        ("Qual a diferença entre shared-assistant e shared-coder?",
         "shared-assistant (dolphin-llama3) é sem censura para uso pessoal. shared-coder (qwen2.5-coder) é restrito apenas a programação e recusa pedidos pessoais."),
        
        # WhatsApp
        ("O QR Code do WhatsApp expira rápido, o que fazer?",
         "Use a engine WEBJS em vez de NOWEB. Configure com: -e WHATSAPP_DEFAULT_ENGINE=WEBJS. A engine WEBJS é mais lenta para iniciar mas muito mais estável."),
        
        ("Como enviar mensagem pelo WAHA?",
         'POST http://192.168.15.2:3001/api/sendText com body: {"session":"default","chatId":"5511999999999@s.whatsapp.net","text":"Sua mensagem"}'),
        
        # Comandos
        ("Quais comandos do Telegram bot estão disponíveis?",
         "Comandos: /models (lista modelos), /profiles (lista perfis), /profile <nome> (usa perfil), /auto_profile (ativa auto-seleção), /use <modelo> (usa modelo específico)"),
        
        # Infraestrutura
        ("Onde ficam os serviços do Shared?",
         "Ollama: 192.168.15.2:11434, Open WebUI: 192.168.15.2:3000, WAHA: 192.168.15.2:3001, Streamlit: localhost:8502"),
    ]
    
    for question, answer in qa_pairs:
        training_pairs.append({
            "prompt": question,
            "completion": answer
        })
    
    return training_pairs

def index_to_chromadb():
    """Indexa conhecimento no ChromaDB para RAG"""
    print("📚 Conectando ao ChromaDB...")
    
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    # Criar ou obter coleção
    collection = client.get_or_create_collection(
        name="shared_knowledge",
        metadata={"description": "Conhecimento do Shared AI"}
    )
    
    print(f"📊 Coleção atual tem {collection.count()} documentos")
    
    # Preparar documentos
    documents = []
    metadatas = []
    ids = []
    
    for item in CURRENT_SESSION_KNOWLEDGE:
        doc_id = hashlib.md5(item["topic"].encode()).hexdigest()
        
        documents.append(f"{item['topic']}\n\n{item['content']}")
        metadatas.append({
            "topic": item["topic"],
            "tags": ",".join(item["tags"]),
            "date": datetime.now().isoformat()
        })
        ids.append(doc_id)
    
    # Adicionar documentos
    print(f"📝 Adicionando {len(documents)} documentos...")
    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    print(f"✅ ChromaDB atualizado! Total: {collection.count()} documentos")
    return collection.count()

def save_training_file():
    """Salva arquivo JSONL de treinamento"""
    training_data = generate_training_data()
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = TRAINING_DIR / f"training_{timestamp}_session.jsonl"
    
    with open(filename, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    print(f"✅ Arquivo de treino salvo: {filename}")
    print(f"   Total de pares: {len(training_data)}")
    return filename

def update_docs_readme():
    """Atualiza README da pasta docs"""
    readme_content = """# 📚 Documentação Shared AI

## Documentos Disponíveis

| Arquivo | Descrição |
|---------|-----------|
| [INTEGRATION.md](INTEGRATION.md) | Integração Open WebUI, Telegram, WhatsApp |
| [MODELS.md](MODELS.md) | Configuração de modelos Ollama |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitetura do sistema |
| [API.md](API.md) | Documentação de APIs |
| [SETUP.md](SETUP.md) | Guia de instalação |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Solução de problemas |

## Atualizações Recentes

### 10 de janeiro de 2026
- ✅ Integração Open WebUI + Telegram + WhatsApp
- ✅ Modelos shared-assistant (sem censura) e shared-coder (restrito)
- ✅ WAHA instalado para API WhatsApp
- ✅ Sistema de perfis automáticos

## Links Úteis

- **Open WebUI:** http://192.168.15.2:3000
- **Ollama:** http://192.168.15.2:11434
- **WAHA Dashboard:** http://192.168.15.2:3001/dashboard
- **GitHub Agent:** http://localhost:8502

---
*Gerado automaticamente*
"""
    
    readme_path = DOCS_DIR / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print(f"✅ README atualizado: {readme_path}")

def main():
    print("🚀 Iniciando atualização de documentação, treino e RAG...")
    print("=" * 60)
    
    # 1. Atualizar docs
    print("\n📖 Atualizando documentação...")
    update_docs_readme()
    
    # 2. Salvar arquivo de treino
    print("\n🎓 Gerando dados de treinamento...")
    training_file = save_training_file()
    
    # 3. Indexar no ChromaDB
    print("\n🔍 Indexando no RAG (ChromaDB)...")
    try:
        doc_count = index_to_chromadb()
    except Exception as e:
        print(f"⚠️ Erro ao indexar: {e}")
        doc_count = 0
    
    print("\n" + "=" * 60)
    print("✅ Atualização concluída!")
    print(f"   📚 Documentos RAG: {doc_count}")
    print(f"   📝 Arquivo treino: {training_file}")

if __name__ == "__main__":
    main()
