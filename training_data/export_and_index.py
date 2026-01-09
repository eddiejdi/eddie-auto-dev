#!/usr/bin/env python3
"""
Exporta conversas do VSCode Copilot e indexa no RAG
"""

import os
import json
import sqlite3
import requests
from pathlib import Path
from datetime import datetime

# Configurações
RAG_API = "http://192.168.15.2:8001/api/v1"
TODAY = datetime.now().strftime("%Y-%m-%d")
CHATS_DIR = Path("/home/eddie/myClaude/training_data/chats_raw")

# Caminhos do VSCode (Windows via WSL)
VSCODE_GLOBAL_DB = "/mnt/c/Users/DELL LATITUDE 5480/AppData/Roaming/Code/User/globalStorage/state.vscdb"
CLAUDE_DEV_DIR = "/mnt/c/Users/DELL LATITUDE 5480/AppData/Roaming/Code/User/globalStorage/saoudrizwan.claude-dev/tasks"

def extract_from_vscdb():
    """Extrai conversas do banco SQLite do VSCode"""
    conversations = []
    
    if not os.path.exists(VSCODE_GLOBAL_DB):
        print(f"⚠️ Banco não encontrado: {VSCODE_GLOBAL_DB}")
        return conversations
    
    try:
        conn = sqlite3.connect(VSCODE_GLOBAL_DB)
        cursor = conn.cursor()
        
        # Buscar chaves relacionadas a chat
        cursor.execute("""
            SELECT key, value FROM ItemTable 
            WHERE key LIKE '%chat%' OR key LIKE '%copilot%' OR key LIKE '%conversation%'
        """)
        
        for key, value in cursor.fetchall():
            try:
                if value and len(value) > 100:
                    data = json.loads(value)
                    if isinstance(data, dict):
                        # Extrair conversas de diferentes formatos
                        if 'messages' in data:
                            for msg in data['messages']:
                                if isinstance(msg, dict) and 'content' in msg:
                                    conversations.append({
                                        'key': key,
                                        'content': msg.get('content', ''),
                                        'role': msg.get('role', 'unknown')
                                    })
                        elif 'requests' in data:
                            for req in data['requests']:
                                if 'message' in req and 'response' in req:
                                    conversations.append({
                                        'prompt': str(req.get('message', '')),
                                        'response': str(req.get('response', '')),
                                        'source': key
                                    })
            except:
                continue
        
        conn.close()
        print(f"📊 Extraídas {len(conversations)} entradas do VSCode DB")
        
    except Exception as e:
        print(f"❌ Erro ao ler VSCode DB: {e}")
    
    return conversations

def extract_from_claude_dev():
    """Extrai conversas do Claude Dev (Cline)"""
    conversations = []
    
    if not os.path.exists(CLAUDE_DEV_DIR):
        print(f"⚠️ Diretório Claude Dev não encontrado")
        return conversations
    
    try:
        for task_dir in Path(CLAUDE_DEV_DIR).iterdir():
            if task_dir.is_dir():
                history_file = task_dir / "api_conversation_history.json"
                if history_file.exists():
                    try:
                        with open(history_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        if isinstance(data, list):
                            for i in range(0, len(data)-1, 2):
                                if i+1 < len(data):
                                    user_msg = data[i]
                                    assistant_msg = data[i+1]
                                    
                                    prompt = ""
                                    response = ""
                                    
                                    if isinstance(user_msg, dict) and user_msg.get('role') == 'user':
                                        content = user_msg.get('content', [])
                                        if isinstance(content, list):
                                            prompt = ' '.join([c.get('text', '') for c in content if isinstance(c, dict)])
                                        else:
                                            prompt = str(content)
                                    
                                    if isinstance(assistant_msg, dict) and assistant_msg.get('role') == 'assistant':
                                        content = assistant_msg.get('content', [])
                                        if isinstance(content, list):
                                            response = ' '.join([c.get('text', '') for c in content if isinstance(c, dict)])
                                        else:
                                            response = str(content)
                                    
                                    if prompt and response:
                                        conversations.append({
                                            'prompt': prompt[:2000],
                                            'response': response[:5000],
                                            'source': f"claude_dev/{task_dir.name}"
                                        })
                    except Exception as e:
                        print(f"  ⚠️ Erro em {history_file}: {e}")
                        
    except Exception as e:
        print(f"❌ Erro ao ler Claude Dev: {e}")
    
    print(f"📊 Extraídas {len(conversations)} conversas do Claude Dev")
    return conversations

def extract_from_chats_raw():
    """Extrai conversas dos JSONs em chats_raw"""
    conversations = []
    
    if not CHATS_DIR.exists():
        print(f"⚠️ Diretório chats_raw não encontrado")
        return conversations
    
    for json_file in CHATS_DIR.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            requests_list = data.get('requests', [])
            
            for req in requests_list:
                try:
                    # Extrair pergunta
                    prompt = ""
                    if 'message' in req:
                        msg = req['message']
                        if isinstance(msg, dict):
                            prompt = msg.get('text', msg.get('content', ''))
                        else:
                            prompt = str(msg)
                    
                    # Extrair resposta
                    response = ""
                    if 'response' in req:
                        resp = req['response']
                        if isinstance(resp, list):
                            parts = []
                            for p in resp:
                                if isinstance(p, dict):
                                    parts.append(p.get('value', p.get('content', '')))
                            response = '\n'.join(filter(None, parts))
                        elif isinstance(resp, dict):
                            response = resp.get('value', resp.get('content', str(resp)))
                        else:
                            response = str(resp)
                    
                    prompt = prompt.strip()
                    response = response.strip()
                    
                    if prompt and response and len(prompt) > 5 and len(response) > 20:
                        conversations.append({
                            'prompt': prompt[:2000],
                            'response': response[:8000],
                            'source': json_file.name
                        })
                except:
                    continue
                    
        except Exception as e:
            print(f"  ⚠️ Erro em {json_file.name}: {e}")
    
    print(f"📊 Extraídas {len(conversations)} conversas de chats_raw")
    return conversations

def save_conversations(conversations, filename=None):
    """Salva conversas em JSONL para treinamento"""
    if not filename:
        filename = f"/home/eddie/myClaude/training_data/training_{TODAY}.jsonl"
    
    with open(filename, 'w', encoding='utf-8') as f:
        for conv in conversations:
            if 'prompt' in conv and 'response' in conv:
                entry = {
                    "messages": [
                        {"role": "user", "content": conv['prompt']},
                        {"role": "assistant", "content": conv['response']}
                    ],
                    "source": conv.get('source', 'unknown'),
                    "date": TODAY
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    print(f"💾 Salvo: {filename}")
    return filename

def index_to_rag(conversations):
    """Indexa conversas no RAG"""
    print(f"\n📤 Indexando {len(conversations)} conversas no RAG...")
    
    documents = []
    for i, conv in enumerate(conversations):
        if 'prompt' in conv and 'response' in conv:
            doc = {
                "id": f"chat_{TODAY}_{i:04d}",
                "content": f"## Pergunta:\n{conv['prompt']}\n\n## Resposta:\n{conv['response']}",
                "metadata": {
                    "type": "conversation",
                    "source": conv.get('source', 'vscode'),
                    "date": TODAY
                }
            }
            documents.append(doc)
    
    # Enviar em lotes
    batch_size = 10
    success = 0
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        
        try:
            # Tentar endpoint de índice
            r = requests.post(
                f"{RAG_API}/rag/index",
                json={"documents": batch, "collection": "chat_history"},
                timeout=60
            )
            
            if r.status_code == 200:
                success += len(batch)
                print(f"  ✅ Batch {i//batch_size + 1}: {len(batch)} docs")
            else:
                # Tentar collection default
                r2 = requests.post(
                    f"{RAG_API}/rag/index",
                    json={"documents": batch, "collection": "default"},
                    timeout=60
                )
                if r2.status_code == 200:
                    success += len(batch)
                    print(f"  ✅ Batch {i//batch_size + 1}: {len(batch)} docs (default)")
                else:
                    print(f"  ⚠️ Batch {i//batch_size + 1}: {r.status_code}")
                    
        except Exception as e:
            print(f"  ❌ Erro batch {i//batch_size + 1}: {e}")
    
    return success

def learn_via_ollama(conversations):
    """Cria contexto para o modelo Ollama aprender"""
    print("\n🧠 Preparando conhecimento para Ollama...")
    
    # Criar arquivo de contexto
    context_file = f"/home/eddie/myClaude/training_data/knowledge_{TODAY}.txt"
    
    with open(context_file, 'w', encoding='utf-8') as f:
        f.write(f"# Conhecimento Aprendido - {TODAY}\n\n")
        
        for i, conv in enumerate(conversations[:100]):  # Top 100
            if 'prompt' in conv and 'response' in conv:
                f.write(f"## Conversa {i+1}\n")
                f.write(f"**Pergunta:** {conv['prompt'][:500]}\n\n")
                f.write(f"**Resposta:** {conv['response'][:1500]}\n\n")
                f.write("---\n\n")
    
    print(f"💾 Contexto salvo: {context_file}")
    return context_file

def main():
    print("=" * 60)
    print(f"🤖 Exportação e Indexação de Conversas - {TODAY}")
    print("=" * 60)
    
    all_conversations = []
    
    # 1. Extrair de chats_raw
    print("\n📥 Extraindo de chats_raw...")
    all_conversations.extend(extract_from_chats_raw())
    
    # 2. Extrair do Claude Dev
    print("\n📥 Extraindo do Claude Dev...")
    all_conversations.extend(extract_from_claude_dev())
    
    # 3. Extrair do VSCode DB
    print("\n📥 Extraindo do VSCode DB...")
    all_conversations.extend(extract_from_vscdb())
    
    print(f"\n📊 Total: {len(all_conversations)} conversas")
    
    if not all_conversations:
        print("❌ Nenhuma conversa encontrada!")
        return
    
    # Remover duplicatas por hash do prompt
    seen = set()
    unique = []
    for conv in all_conversations:
        if 'prompt' in conv:
            key = conv['prompt'][:100]
            if key not in seen:
                seen.add(key)
                unique.append(conv)
    
    print(f"🔄 Após deduplicação: {len(unique)} conversas únicas")
    
    # Mostrar amostras
    print("\n📋 Amostras:")
    for conv in unique[:3]:
        if 'prompt' in conv:
            print(f"  Q: {conv['prompt'][:80]}...")
            print(f"  A: {conv.get('response', '')[:80]}...")
            print()
    
    # Salvar para treinamento
    print("\n💾 Salvando para treinamento...")
    save_conversations(unique)
    
    # Criar contexto para Ollama
    learn_via_ollama(unique)
    
    # Verificar se RAG está online
    print("\n🔍 Verificando RAG API...")
    try:
        r = requests.get(f"{RAG_API.replace('/api/v1', '')}/health", timeout=5)
        print(f"   Status: {r.status_code}")
        
        # Indexar no RAG
        indexed = index_to_rag(unique)
        print(f"\n✅ {indexed} documentos indexados no RAG")
        
    except Exception as e:
        print(f"   ⚠️ RAG offline: {e}")
        print("   Conversas salvas localmente para indexação posterior")
    
    print("\n" + "=" * 60)
    print("🎉 EXPORTAÇÃO CONCLUÍDA!")
    print("=" * 60)

if __name__ == "__main__":
    main()
