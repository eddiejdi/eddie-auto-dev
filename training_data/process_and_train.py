#!/usr/bin/env python3
"""
Processador de Chats do VS Code para Treinamento
"""

import os
import json
import glob
from pathlib import Path
from datetime import datetime
import requests

# Configurações
OLLAMA_HOST = "http://192.168.15.2:11434"
BASE_DIR = Path("/home/eddie/myClaude/training_data")
CHATS_DIR = BASE_DIR / "chats_raw"
TODAY = datetime.now().strftime("%Y-%m-%d")

def load_all_chats():
    """Carrega todos os chats do diretório"""
    chats = []
    
    for chat_file in CHATS_DIR.glob("*.json"):
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chats.append({
                    'file': str(chat_file),
                    'name': chat_file.stem,
                    'data': data
                })
                print(f"✅ Carregado: {chat_file.name}")
        except Exception as e:
            print(f"⚠️ Erro em {chat_file.name}: {e}")
    
    return chats

def extract_conversations(chats):
    """Extrai pares de prompt/resposta dos chats"""
    conversations = []
    
    for chat in chats:
        data = chat['data']
        
        # Formato VS Code Copilot Chat
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
                    
                    # Pode ser uma lista de partes
                    if isinstance(resp, list):
                        parts = []
                        for part in resp:
                            if isinstance(part, dict):
                                parts.append(part.get('value', part.get('content', '')))
                            else:
                                parts.append(str(part))
                        response_text = '\n'.join(parts)
                    
                    # Ou pode ser um dict com 'value'
                    elif isinstance(resp, dict):
                        if 'value' in resp:
                            val = resp['value']
                            if isinstance(val, list):
                                parts = []
                                for v in val:
                                    if isinstance(v, dict):
                                        parts.append(v.get('value', v.get('content', '')))
                                    else:
                                        parts.append(str(v))
                                response_text = '\n'.join(parts)
                            else:
                                response_text = str(val)
                        else:
                            response_text = resp.get('content', resp.get('text', str(resp)))
                    else:
                        response_text = str(resp)
                
                # Limpar e validar
                prompt = prompt.strip()
                response_text = response_text.strip()
                
                if prompt and response_text and len(prompt) > 5 and len(response_text) > 10:
                    conversations.append({
                        'prompt': prompt,
                        'response': response_text,
                        'source': chat['name']
                    })
                    
            except Exception as e:
                continue
    
    return conversations

def create_training_data(conversations):
    """Cria arquivo JSONL para treinamento"""
    output_file = BASE_DIR / f"training_{TODAY}.jsonl"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for conv in conversations:
            item = {
                "instruction": conv['prompt'],
                "output": conv['response'],
                "input": ""
            }
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    print(f"\n📝 Arquivo de treinamento: {output_file}")
    print(f"   {len(conversations)} exemplos de treinamento")
    
    return output_file, conversations

def create_enhanced_modelfile(conversations, base_model="codestral:22b"):
    """Cria Modelfile com contexto aprendido"""
    
    # Criar resumo dos tópicos abordados
    topics = set()
    for conv in conversations[:50]:  # Análise das primeiras 50
        prompt_lower = conv['prompt'].lower()
        
        if any(w in prompt_lower for w in ['python', 'pip', 'venv']):
            topics.add("Python e ambientes virtuais")
        if any(w in prompt_lower for w in ['github', 'git', 'repo', 'commit']):
            topics.add("GitHub e controle de versão")
        if any(w in prompt_lower for w in ['ollama', 'llm', 'model', 'train']):
            topics.add("Ollama e modelos de linguagem")
        if any(w in prompt_lower for w in ['docker', 'container', 'kubernetes']):
            topics.add("Docker e containerização")
        if any(w in prompt_lower for w in ['api', 'rest', 'http', 'request']):
            topics.add("APIs e requisições HTTP")
        if any(w in prompt_lower for w in ['streamlit', 'flask', 'web']):
            topics.add("Desenvolvimento web")
        if any(w in prompt_lower for w in ['mcp', 'server', 'protocol']):
            topics.add("MCP e protocolos de integração")
        if any(w in prompt_lower for w in ['linux', 'bash', 'ssh', 'terminal']):
            topics.add("Linux e linha de comando")
    
    topics_str = '\n'.join([f"- {t}" for t in sorted(topics)])
    
    # Exemplos de interações (resumidos)
    examples = []
    for conv in conversations[:5]:
        prompt_short = conv['prompt'][:150] + "..." if len(conv['prompt']) > 150 else conv['prompt']
        examples.append(f"Usuário: {prompt_short}")
    examples_str = '\n'.join(examples)
    
    modelfile = f'''FROM {base_model}

SYSTEM """Você é Eddie Assistant, um assistente de programação altamente especializado.
Você foi treinado com {len(conversations)} conversas reais de desenvolvimento do dia {TODAY}.

## Áreas de Especialização (baseado no treinamento de hoje):
{topics_str}

## Contexto de Aprendizado:
Este modelo foi personalizado com interações reais incluindo:
{examples_str}

## Diretrizes:
1. Forneça código funcional e testado
2. Explique o raciocínio por trás das soluções
3. Use boas práticas de programação
4. Seja conciso mas completo
5. Responda em português quando perguntado em português
6. Para código, use markdown com syntax highlighting

## Ambiente do Usuário:
- Sistema: WSL Ubuntu no Windows
- Servidor Ollama: 192.168.15.2:11434
- Modelos disponíveis: codestral:22b, deepseek-coder-v2:16b, qwen2.5-coder:7b
- Ferramentas: VS Code, GitHub, Docker
"""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
PARAMETER repeat_penalty 1.1
'''
    return modelfile

def train_model(conversations, base_model="codestral:22b"):
    """Cria modelo personalizado no Ollama"""
    
    model_name = f"eddie-assistant:{TODAY}"
    
    print(f"\n🚀 Criando modelo {model_name}...")
    print(f"   Base: {base_model}")
    print(f"   Conversas: {len(conversations)}")
    
    # Criar Modelfile
    modelfile = create_enhanced_modelfile(conversations, base_model)
    
    # Salvar Modelfile
    modelfile_path = BASE_DIR / "Modelfile.latest"
    with open(modelfile_path, 'w', encoding='utf-8') as f:
        f.write(modelfile)
    print(f"📄 Modelfile salvo: {modelfile_path}")
    
    # Criar modelo via API
    try:
        print("\n⏳ Enviando para Ollama...")
        response = requests.post(
            f"{OLLAMA_HOST}/api/create",
            json={
                "name": model_name,
                "modelfile": modelfile
            },
            timeout=300,
            stream=True
        )
        
        for line in response.iter_lines():
            if line:
                try:
                    status = json.loads(line)
                    if 'status' in status:
                        print(f"   {status['status']}")
                except:
                    pass
        
        print(f"\n✅ Modelo {model_name} criado com sucesso!")
        return model_name
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Não foi possível conectar ao Ollama em {OLLAMA_HOST}")
        print("   Verifique se o servidor está rodando.")
        return None
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def update_continue_config(model_name):
    """Atualiza configuração do Continue para usar o novo modelo"""
    config_path = Path.home() / ".continue" / "config.json"
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Adicionar novo modelo à lista
            new_model = {
                "title": f"Eddie Assistant ({TODAY})",
                "provider": "ollama",
                "model": model_name,
                "apiBase": OLLAMA_HOST
            }
            
            if 'models' in config:
                # Verificar se já existe
                exists = any(m.get('model') == model_name for m in config['models'])
                if not exists:
                    config['models'].insert(0, new_model)
                    
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    print(f"📝 Continue atualizado com {model_name}")
        except Exception as e:
            print(f"⚠️ Erro ao atualizar Continue: {e}")

def main():
    print("=" * 60)
    print(f"🤖 Processamento de Chats e Treinamento - {TODAY}")
    print("=" * 60)
    
    # Verificar diretório de chats
    if not CHATS_DIR.exists():
        print(f"❌ Diretório não encontrado: {CHATS_DIR}")
        return
    
    # Carregar chats
    print("\n📥 Carregando chats...")
    chats = load_all_chats()
    
    if not chats:
        print("❌ Nenhum chat encontrado!")
        return
    
    print(f"\n✅ {len(chats)} arquivos carregados")
    
    # Extrair conversas
    print("\n🔍 Extraindo conversas...")
    conversations = extract_conversations(chats)
    
    if not conversations:
        print("❌ Nenhuma conversa válida extraída!")
        return
    
    print(f"💬 {len(conversations)} conversas extraídas")
    
    # Mostrar algumas amostras
    print("\n📋 Amostras de conversas:")
    for i, conv in enumerate(conversations[:3]):
        print(f"\n  [{i+1}] Prompt: {conv['prompt'][:80]}...")
        print(f"      Response: {conv['response'][:80]}...")
    
    # Criar dados de treinamento
    print("\n📝 Criando dados de treinamento...")
    training_file, convs = create_training_data(conversations)
    
    # Treinar modelo
    model_name = train_model(conversations)
    
    if model_name:
        # Atualizar Continue
        update_continue_config(model_name)
        
        print("\n" + "=" * 60)
        print("🎉 TREINAMENTO CONCLUÍDO!")
        print("=" * 60)
        print(f"\n📦 Modelo: {model_name}")
        print(f"📊 Conversas: {len(conversations)}")
        print(f"📂 Dados: {BASE_DIR}")
        print(f"\n💡 Para usar:")
        print(f"   ollama run {model_name}")

if __name__ == "__main__":
    main()
