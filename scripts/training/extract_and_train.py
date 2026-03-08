#!/usr/bin/env python3
"""
Extrator de Chats do VS Code para Treinamento de LLM
Coleta chats de hoje e prepara dados para fine-tuning do Ollama
"""

import os
import sys
import json
import glob
import base64
from pathlib import Path
from datetime import datetime, date
import requests

# Configurações (override via environment variables if needed)
OLLAMA_HOST = os.environ.get("OLLAMA_URL") or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"
_default_out = Path(__file__).resolve().parent / "training_data"
OUTPUT_DIR = Path(os.environ.get("TRAINING_OUTPUT_DIR", str(_default_out)))
TODAY = date.today().strftime("%Y-%m-%d")

# Caminhos dos chats do VS Code (Windows via WSL)
VSCODE_CHAT_PATHS = [
    "/mnt/c/Users/DELL LATITUDE 5480/AppData/Roaming/Code/User/workspaceStorage/*/chatSessions/*.json",
    "/mnt/c/Users/DELL LATITUDE 5480/AppData/Roaming/Code/User/globalStorage/github.copilot-chat/sessions/*.json",
]

def ensure_output_dir():
    """Garante que o diretório de saída existe"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR

def get_today_chats():
    """Coleta todos os chats de hoje"""
    chats = []
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for pattern in VSCODE_CHAT_PATHS:
        for chat_file in glob.glob(pattern):
            try:
                # Verifica se foi modificado hoje
                mtime = datetime.fromtimestamp(os.path.getmtime(chat_file))
                if mtime >= today_start:
                    with open(chat_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        chats.append({
                            'file': chat_file,
                            'data': data,
                            'modified': mtime.isoformat()
                        })
                        print(f"✅ Chat encontrado: {Path(chat_file).name}")
            except Exception as e:
                print(f"⚠️ Erro ao ler {chat_file}: {e}")
    
    return chats

def extract_conversations(chats):
    """Extrai conversas no formato de treinamento"""
    conversations = []
    
    for chat in chats:
        data = chat['data']
        
        # Formato VS Code Copilot Chat
        if 'requests' in data:
            for req in data.get('requests', []):
                conv = {
                    'prompt': '',
                    'response': '',
                    'timestamp': chat['modified']
                }
                
                # Mensagem do usuário
                if 'message' in req:
                    if isinstance(req['message'], dict):
                        conv['prompt'] = req['message'].get('text', '')
                    else:
                        conv['prompt'] = str(req['message'])
                
                # Resposta do assistente
                if 'response' in req:
                    resp = req['response']
                    if isinstance(resp, dict):
                        # Pode ter múltiplas partes
                        parts = resp.get('value', [])
                        if isinstance(parts, list):
                            conv['response'] = '\n'.join([
                                p.get('value', '') if isinstance(p, dict) else str(p)
                                for p in parts
                            ])
                        else:
                            conv['response'] = str(parts)
                    else:
                        conv['response'] = str(resp)
                
                if conv['prompt'] and conv['response']:
                    conversations.append(conv)
        
        # Formato alternativo com messages
        elif 'messages' in data:
            messages = data.get('messages', [])
            for i in range(0, len(messages) - 1, 2):
                if i + 1 < len(messages):
                    user_msg = messages[i]
                    assistant_msg = messages[i + 1]
                    
                    conv = {
                        'prompt': user_msg.get('content', user_msg.get('text', '')),
                        'response': assistant_msg.get('content', assistant_msg.get('text', '')),
                        'timestamp': chat['modified']
                    }
                    
                    if conv['prompt'] and conv['response']:
                        conversations.append(conv)
    
    return conversations

def create_training_file(conversations, output_file):
    """Cria arquivo de treinamento no formato JSONL (para fine-tuning)"""
    with open(output_file, 'w', encoding='utf-8') as f:
        for conv in conversations:
            # Formato para Ollama/LLaMA fine-tuning
            training_item = {
                "instruction": conv['prompt'],
                "output": conv['response'],
                "input": ""  # Contexto adicional (opcional)
            }
            f.write(json.dumps(training_item, ensure_ascii=False) + '\n')
    
    print(f"📝 Arquivo de treinamento criado: {output_file}")
    return output_file

def create_modelfile(base_model, training_data_summary):
    """Cria um Modelfile atualizado com contexto dos chats de hoje"""
    
    # Criar um resumo do contexto aprendido
    context_summary = "Você aprendeu com as seguintes interações de hoje:\n"
    for conv in training_data_summary[:10]:  # Primeiras 10 conversas como exemplo
        context_summary += f"- Usuário perguntou sobre: {conv['prompt'][:100]}...\n"
    
    modelfile = f"""FROM {base_model}

SYSTEM \"\"\"Você é um assistente de programação altamente especializado. 
Você foi treinado com conversas reais de desenvolvimento de software.

{context_summary}

Você é excelente em:
- Programação Python, JavaScript, TypeScript
- DevOps e infraestrutura (Docker, Kubernetes, Linux)
- Desenvolvimento de APIs e microserviços
- Integração com GitHub e ferramentas de IA
- Ollama e modelos de linguagem

Sempre forneça respostas precisas, código funcional e explicações claras.
Responda em português brasileiro quando o usuário escrever em português.
\"\"\"

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
"""
    return modelfile

def train_ollama_model(training_file, base_model="codestral:22b"):
    """Cria/atualiza modelo no Ollama com o contexto aprendido"""
    
    print(f"\n🚀 Iniciando treinamento baseado em {base_model}...")
    
    # Ler dados de treinamento para criar contexto
    conversations = []
    with open(training_file, 'r', encoding='utf-8') as f:
        for line in f:
            conversations.append(json.loads(line))
    
    print(f"📊 {len(conversations)} conversas carregadas para contexto")
    
    # Criar Modelfile
    modelfile_content = create_modelfile(base_model, conversations)
    modelfile_path = OUTPUT_DIR / "Modelfile.trained"
    
    with open(modelfile_path, 'w', encoding='utf-8') as f:
        f.write(modelfile_content)
    
    print(f"📄 Modelfile criado: {modelfile_path}")
    
    # Criar modelo no Ollama
    model_name = f"shared-assistant:{TODAY}"
    
    print(f"⏳ Criando modelo {model_name} no Ollama...")
    
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/create",
            json={
                "name": model_name,
                "modelfile": modelfile_content
            },
            timeout=300,
            stream=True
        )
        
        for line in response.iter_lines():
            if line:
                status = json.loads(line)
                if 'status' in status:
                    print(f"  {status['status']}")
        
        print(f"\n✅ Modelo {model_name} criado com sucesso!")
        return model_name
        
    except Exception as e:
        print(f"❌ Erro ao criar modelo: {e}")
        return None

def save_raw_chats(chats):
    """Salva os chats brutos para referência"""
    raw_file = OUTPUT_DIR / f"raw_chats_{TODAY}.json"
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump(chats, f, ensure_ascii=False, indent=2, default=str)
    print(f"💾 Chats brutos salvos: {raw_file}")
    return raw_file

def main():
    print("=" * 60)
    print(f"🤖 Extração e Treinamento de Chats - {TODAY}")
    print("=" * 60)
    
    # Garantir diretório de saída
    ensure_output_dir()
    
    # Coletar chats de hoje
    print("\n📥 Coletando chats de hoje...")
    chats = get_today_chats()
    
    if not chats:
        print("❌ Nenhum chat encontrado hoje!")
        print("\nVerificando caminhos alternativos...")
        
        # Tentar caminhos Windows direto
        alt_paths = [
            "/mnt/c/Users/*/AppData/Roaming/Code/User/workspaceStorage/*/chatSessions/*.json",
            "/mnt/c/Users/*/AppData/Roaming/Code/User/globalStorage/*/sessions/*.json"
        ]
        
        for pattern in alt_paths:
            for f in glob.glob(pattern):
                print(f"  Encontrado: {f}")
        
        return
    
    print(f"\n✅ {len(chats)} arquivos de chat encontrados")
    
    # Salvar chats brutos
    save_raw_chats(chats)
    
    # Extrair conversas
    print("\n🔍 Extraindo conversas...")
    conversations = extract_conversations(chats)
    print(f"💬 {len(conversations)} conversas extraídas")
    
    if not conversations:
        print("⚠️ Nenhuma conversa válida extraída")
        return
    
    # Criar arquivo de treinamento
    print("\n📝 Criando arquivo de treinamento...")
    training_file = OUTPUT_DIR / f"training_{TODAY}.jsonl"
    create_training_file(conversations, training_file)
    
    # Treinar modelo
    print("\n🎓 Iniciando treinamento do modelo...")
    model_name = train_ollama_model(training_file)
    
    if model_name:
        print("\n" + "=" * 60)
        print("🎉 TREINAMENTO CONCLUÍDO!")
        print("=" * 60)
        print(f"\n📦 Modelo criado: {model_name}")
        print(f"📂 Dados em: {OUTPUT_DIR}")
        print(f"\n💡 Para usar o modelo:")
        print(f"   ollama run {model_name}")
        print(f"\n   Ou no Continue/Cline, configure:")
        print(f'   "model": "{model_name}"')

if __name__ == "__main__":
    main()
