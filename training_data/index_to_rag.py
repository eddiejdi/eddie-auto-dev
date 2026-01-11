#!/usr/bin/env python3
"""
Indexa chats de hoje no RAG existente (personaIDE)
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime

# Configurações
RAG_API = "http://192.168.15.2:8001/api/v1"
CHATS_DIR = Path("/home/homelab/myClaude/training_data/chats_raw")
TODAY = datetime.now().strftime("%Y-%m-%d")

def load_chats():
    """Carrega todos os chats"""
    chats = []
    for f in CHATS_DIR.glob("*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                chats.append({'file': f.name, 'data': data})
                print(f"✅ Carregado: {f.name}")
        except Exception as e:
            print(f"⚠️ Erro em {f.name}: {e}")
    return chats

def extract_conversations(chats):
    """Extrai conversas dos chats"""
    conversations = []
    
    for chat in chats:
        data = chat['data']
        requests_list = data.get('requests', [])
        
        for req in requests_list:
            try:
                # Extrair mensagem do usuário
                prompt = ""
                if 'message' in req:
                    msg = req['message']
                    if isinstance(msg, dict):
                        prompt = msg.get('text', msg.get('content', ''))
                    else:
                        prompt = str(msg)
                
                # Extrair resposta
                response_text = ""
                if 'response' in req:
                    resp = req['response']
                    if isinstance(resp, list):
                        parts = [p.get('value', p.get('content', '')) if isinstance(p, dict) else str(p) for p in resp]
                        response_text = '\n'.join(parts)
                    elif isinstance(resp, dict):
                        if 'value' in resp:
                            val = resp['value']
                            if isinstance(val, list):
                                parts = [v.get('value', v.get('content', '')) if isinstance(v, dict) else str(v) for v in val]
                                response_text = '\n'.join(parts)
                            else:
                                response_text = str(val)
                        else:
                            response_text = resp.get('content', resp.get('text', str(resp)))
                    else:
                        response_text = str(resp)
                
                prompt = prompt.strip()
                response_text = response_text.strip()
                
                if prompt and response_text and len(prompt) > 5 and len(response_text) > 10:
                    conversations.append({
                        'prompt': prompt,
                        'response': response_text,
                        'source': chat['file']
                    })
            except:
                continue
    
    return conversations

def index_to_rag(conversations):
    """Indexa conversas no RAG"""
    
    print(f"\n📤 Indexando {len(conversations)} conversas no RAG...")
    
    # Criar documentos no formato esperado pelo RAG (DocumentChunk)
    documents = []
    
    for i, conv in enumerate(conversations):
        doc = {
            "id": f"chat_{TODAY}_{i:04d}",
            "content": f"## Pergunta:\n{conv['prompt']}\n\n## Resposta:\n{conv['response']}",
            "metadata": {
                "type": "conversation",
                "source": conv['source'],
                "date": TODAY,
                "file_path": f"/chats/{conv['source']}",
                "language": "pt-br"
            }
        }
        documents.append(doc)
    
    # Indexar em lotes
    print("\n🔄 Enviando para RAG API...")
    batch_size = 10
    success_count = 0
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{RAG_API}/rag/index",
                json={
                    "documents": batch,
                    "collection": "chat_history"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                success_count += len(batch)
                print(f"  ✅ Batch {i//batch_size + 1}: {len(batch)} documentos indexados")
            else:
                print(f"  ⚠️ Batch {i//batch_size + 1}: Status {response.status_code}")
                # Tentar collection default se falhar
                response2 = requests.post(
                    f"{RAG_API}/rag/index",
                    json={
                        "documents": batch,
                        "collection": "default"
                    },
                    timeout=60
                )
                if response2.status_code == 200:
                    success_count += len(batch)
                    print(f"  ✅ Batch {i//batch_size + 1}: Indexado em 'default'")
                else:
                    print(f"     Resposta: {response.text[:200]}")
                
        except Exception as e:
            print(f"  ❌ Erro no batch {i//batch_size + 1}: {e}")
    
    return success_count

def learn_via_agent(conversations):
    """Usa o endpoint /rag/agent/learn para aprendizado"""
    
    print("\n🧠 Usando endpoint de aprendizado do agente...")
    
    # Preparar conhecimento para o agente
    knowledge = []
    
    for conv in conversations[:50]:  # Primeiras 50 para não sobrecarregar
        knowledge.append({
            "question": conv['prompt'],
            "answer": conv['response'],
            "context": f"Conversa do dia {TODAY}"
        })
    
    try:
        response = requests.post(
            f"{RAG_API}/rag/agent/learn",
            json={
                "knowledge": knowledge,
                "source": "vscode_chats",
                "date": TODAY
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Agente aprendeu: {result}")
            return True
        else:
            print(f"  ⚠️ Status: {response.status_code}")
            print(f"  Response: {response.text[:300]}")
            return False
            
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False

def check_rag_status():
    """Verifica status do RAG"""
    try:
        response = requests.get(f"{RAG_API}/rag/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(f"\n📊 Status do RAG:")
            print(f"   {json.dumps(stats, indent=2)}")
            return True
    except Exception as e:
        print(f"⚠️ Erro ao verificar status: {e}")
    return False

def main():
    print("=" * 60)
    print(f"🤖 Indexação de Chats no RAG - {TODAY}")
    print("=" * 60)
    
    # Verificar RAG
    print("\n🔍 Verificando RAG API...")
    try:
        r = requests.get(f"{RAG_API.replace('/api/v1', '')}/health", timeout=5)
        print(f"   Health: {r.status_code}")
    except:
        print("   ⚠️ Health check falhou, tentando continuar...")
    
    # Carregar chats
    print("\n📥 Carregando chats...")
    chats = load_chats()
    
    if not chats:
        print("❌ Nenhum chat encontrado!")
        return
    
    # Extrair conversas
    print(f"\n🔍 Extraindo conversas de {len(chats)} arquivos...")
    conversations = extract_conversations(chats)
    print(f"💬 {len(conversations)} conversas extraídas")
    
    if not conversations:
        print("❌ Nenhuma conversa válida!")
        return
    
    # Mostrar amostras
    print("\n📋 Amostras:")
    for conv in conversations[:2]:
        print(f"  Q: {conv['prompt'][:60]}...")
        print(f"  A: {conv['response'][:60]}...")
        print()
    
    # Tentar endpoint de aprendizado do agente primeiro
    agent_success = learn_via_agent(conversations)
    
    # Indexar no RAG
    indexed = index_to_rag(conversations)
    
    # Verificar status final
    check_rag_status()
    
    print("\n" + "=" * 60)
    print("🎉 INDEXAÇÃO CONCLUÍDA!")
    print("=" * 60)
    print(f"📊 Conversas processadas: {len(conversations)}")
    print(f"📤 Documentos indexados: {indexed}")
    print(f"\n💡 Para consultar, use:")
    print(f'   curl -X POST "{RAG_API}/rag/search" -H "Content-Type: application/json" -d \'{{"query": "sua pergunta"}}\'')

if __name__ == "__main__":
    main()
