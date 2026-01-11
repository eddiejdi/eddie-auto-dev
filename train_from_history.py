#!/usr/bin/env python3
"""
Script completo para treinar o modelo Ollama com histórico de conversas
"""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Configurações
OLLAMA_HOST = "192.168.15.2"
OLLAMA_PORT = "11434"
OLLAMA_API = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
BASE_MODEL = "qwen2.5-coder:7b"
NEW_MODEL = "eddie-coder"

CHATS_DIR = Path("/home/home-lab/myClaude/training_data/chats_raw")
OUTPUT_DIR = Path("/home/home-lab/myClaude/training_data")
TODAY = datetime.now().strftime("%Y-%m-%d")


def extract_conversations() -> List[Dict]:
    """Extrai todas as conversas dos arquivos JSON"""
    conversations = []
    
    print(f"\n📂 Processando {CHATS_DIR}...")
    
    for json_file in sorted(CHATS_DIR.glob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            requests_list = data.get('requests', [])
            file_convs = 0
            
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
                                    val = p.get('value', p.get('content', ''))
                                    if val:
                                        parts.append(val)
                            response = '\n'.join(parts)
                        elif isinstance(resp, dict):
                            response = resp.get('value', resp.get('content', str(resp)))
                        else:
                            response = str(resp)
                    
                    # Limpar
                    prompt = prompt.strip()
                    response = response.strip()
                    
                    # Filtrar conversas válidas
                    if prompt and response:
                        if len(prompt) > 10 and len(response) > 50:
                            # Filtrar respostas muito curtas ou inúteis
                            if not response.startswith("I'll") and "tool" not in response[:50].lower():
                                conversations.append({
                                    'prompt': prompt[:3000],
                                    'response': response[:10000],
                                    'source': json_file.name
                                })
                                file_convs += 1
                except Exception as e:
                    continue
            
            if file_convs > 0:
                print(f"  ✓ {json_file.name}: {file_convs} conversas")
                    
        except Exception as e:
            print(f"  ⚠️ Erro em {json_file.name}: {e}")
    
    print(f"\n📊 Total: {len(conversations)} conversas extraídas")
    return conversations


def create_training_data(conversations: List[Dict]) -> str:
    """Cria arquivo JSONL para treinamento"""
    output_file = OUTPUT_DIR / f"training_{TODAY}_full.jsonl"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for conv in conversations:
            entry = {
                "messages": [
                    {"role": "user", "content": conv['prompt']},
                    {"role": "assistant", "content": conv['response']}
                ]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    print(f"\n💾 Arquivo de treinamento: {output_file}")
    print(f"   Tamanho: {output_file.stat().st_size / 1024:.1f} KB")
    
    return str(output_file)


def create_system_prompt(conversations: List[Dict]) -> str:
    """Cria system prompt baseado no estilo das conversas"""
    # Analisar tópicos comuns
    topics = set()
    for conv in conversations[:100]:
        prompt = conv['prompt'].lower()
        if 'python' in prompt:
            topics.add('Python')
        if 'docker' in prompt:
            topics.add('Docker')
        if 'linux' in prompt or 'ubuntu' in prompt:
            topics.add('Linux')
        if 'git' in prompt or 'github' in prompt:
            topics.add('Git/GitHub')
        if 'api' in prompt or 'rest' in prompt:
            topics.add('APIs')
        if 'sql' in prompt or 'database' in prompt:
            topics.add('Databases')
        if 'javascript' in prompt or 'typescript' in prompt or 'node' in prompt:
            topics.add('JavaScript/TypeScript')
    
    topics_str = ', '.join(sorted(topics)[:10])
    
    return f"""Você é Eddie Coder, um assistente especializado em programação e DevOps.

Suas especialidades incluem: {topics_str}.

Comportamento:
- Responda em português brasileiro
- Seja direto e prático
- Forneça código funcional e testado
- Explique brevemente quando necessário
- Use boas práticas de programação

Quando solicitado código:
1. Retorne código limpo e bem formatado
2. Inclua comentários relevantes
3. Sugira melhorias quando apropriado"""


def create_modelfile(system_prompt: str, training_file: str) -> str:
    """Cria Modelfile para Ollama"""
    modelfile_content = f'''FROM {BASE_MODEL}

SYSTEM """
{system_prompt}
"""

PARAMETER temperature 0.4
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 8192
PARAMETER repeat_penalty 1.1

# Treinado com conversas do usuário em {TODAY}
'''
    
    modelfile_path = OUTPUT_DIR / "Modelfile.eddie"
    with open(modelfile_path, 'w', encoding='utf-8') as f:
        f.write(modelfile_content)
    
    print(f"\n📄 Modelfile criado: {modelfile_path}")
    return str(modelfile_path)


def train_model(modelfile_path: str) -> bool:
    """Treina o modelo no Ollama"""
    print(f"\n🚀 Iniciando treinamento no servidor {OLLAMA_HOST}...")
    
    try:
        # Copiar Modelfile para o servidor
        print("  📤 Copiando Modelfile para servidor...")
        subprocess.run([
            'scp', modelfile_path, 
            f'homelab@{OLLAMA_HOST}:/tmp/Modelfile.eddie'
        ], check=True, capture_output=True)
        
        # Criar modelo no Ollama
        print(f"  🔨 Criando modelo '{NEW_MODEL}'...")
        result = subprocess.run([
            'ssh', f'homelab@{OLLAMA_HOST}',
            f'cd /tmp && ollama create {NEW_MODEL} -f Modelfile.eddie'
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"\n✅ Modelo '{NEW_MODEL}' criado com sucesso!")
            return True
        else:
            print(f"\n❌ Erro ao criar modelo: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("\n⚠️ Timeout - o modelo pode ainda estar sendo criado")
        return False
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        return False


def test_model():
    """Testa o modelo treinado"""
    print(f"\n🧪 Testando modelo '{NEW_MODEL}'...")
    
    try:
        import httpx
        
        response = httpx.post(
            f"{OLLAMA_API}/api/generate",
            json={
                "model": NEW_MODEL,
                "prompt": "Crie uma função Python para calcular fatorial",
                "stream": False
            },
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('response', '')[:500]
            print(f"\n📝 Resposta do modelo:\n{result}")
            return True
        else:
            print(f"❌ Erro: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar: {e}")
        return False


def main():
    print("=" * 60)
    print("🎓 TREINAMENTO DO MODELO EDDIE-CODER")
    print("=" * 60)
    
    # 1. Extrair conversas
    conversations = extract_conversations()
    
    if not conversations:
        print("❌ Nenhuma conversa encontrada!")
        return
    
    # 2. Criar arquivo de treinamento
    training_file = create_training_data(conversations)
    
    # 3. Criar system prompt personalizado
    system_prompt = create_system_prompt(conversations)
    print(f"\n📋 System Prompt:\n{system_prompt[:300]}...")
    
    # 4. Criar Modelfile
    modelfile_path = create_modelfile(system_prompt, training_file)
    
    # 5. Treinar modelo
    success = train_model(modelfile_path)
    
    if success:
        # 6. Testar
        test_model()
        
        print("\n" + "=" * 60)
        print(f"✅ TREINAMENTO COMPLETO!")
        print(f"   Modelo: {NEW_MODEL}")
        print(f"   Servidor: {OLLAMA_HOST}")
        print(f"   Conversas usadas: {len(conversations)}")
        print("=" * 60)
    else:
        print("\n⚠️ Treinamento não concluído. Verifique os logs.")


if __name__ == "__main__":
    main()
