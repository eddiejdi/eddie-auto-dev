#!/usr/bin/env python3
"""
Script para extrair conversas do WhatsApp via WAHA e treinar modelo Ollama
"""

import requests
import json
import os
from datetime import datetime

# Configurações WAHA
WAHA_BASE_URL = os.getenv("WAHA_BASE_URL", "http://localhost:3001")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
SESSION_NAME = os.getenv("WAHA_SESSION", "default")
MY_NUMBER = os.getenv("WHATSAPP_NUMBER", "5511981193899")

# Configurações Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://192.168.15.2:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "shared-assistant")

# Headers para requisições WAHA
try:
    if not WAHA_API_KEY:
        from tools.vault.secret_store import get_field
        WAHA_API_KEY = get_field("shared/waha_api_key", "password")
except Exception:
    WAHA_API_KEY = WAHA_API_KEY or ""

headers = {
    "Content-Type": "application/json"
}
if WAHA_API_KEY:
    headers["X-Api-Key"] = WAHA_API_KEY

def get_all_chats():
    """Obtém lista de todos os chats"""
    url = f"{WAHA_BASE_URL}/api/{SESSION_NAME}/chats"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao obter chats: {response.status_code} - {response.text[:200]}")
            return []
    except Exception as e:
        print(f"Erro: {e}")
        return []

def get_chat_messages(chat_id: str, limit: int = 100):
    """Obtém mensagens de um chat específico"""
    # Extrair o ID serializado se for um dicionário
    if isinstance(chat_id, dict):
        chat_id = chat_id.get("_serialized", str(chat_id))
    
    # URL encode o chat_id
    import urllib.parse
    encoded_chat_id = urllib.parse.quote(chat_id, safe='')
    
    url = f"{WAHA_BASE_URL}/api/{SESSION_NAME}/chats/{encoded_chat_id}/messages"
    params = {"limit": limit, "downloadMedia": "false"}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao obter mensagens de {chat_id}: {response.status_code}")
            return []
    except Exception as e:
        print(f"Erro ao obter mensagens: {e}")
        return []

def extract_conversations():
    """Extrai todas as conversas em formato de treinamento"""
    print("🔍 Obtendo lista de chats...")
    chats = get_all_chats()
    
    if not chats:
        print("❌ Nenhum chat encontrado")
        return []
    
    print(f"✅ Encontrados {len(chats)} chats")
    
    all_conversations = []
    
    for chat in chats[:50]:  # Limitar a 50 chats para não sobrecarregar
        chat_id = chat.get("id", "")
        chat_name = chat.get("name", "Desconhecido")
        
        # Pular grupos por enquanto
        if "@g.us" in chat_id:
            continue
        
        print(f"📱 Processando chat: {chat_name}")
        
        messages = get_chat_messages(chat_id, limit=100)
        
        if not messages:
            continue
        
        # Ordenar por timestamp
        messages = sorted(messages, key=lambda x: x.get("timestamp", 0))
        
        # Extrair pares de mensagem/resposta
        conversation_pairs = []
        
        for i, msg in enumerate(messages):
            if not msg.get("body"):
                continue
            
            from_me = msg.get("fromMe", False)
            body = msg.get("body", "").strip()
            
            if not body:
                continue
            
            # Se for mensagem do outro (não minha)
            if not from_me:
                # Procurar minha próxima resposta
                for j in range(i + 1, min(i + 5, len(messages))):
                    next_msg = messages[j]
                    if next_msg.get("fromMe") and next_msg.get("body"):
                        pair = {
                            "user_message": body,
                            "assistant_response": next_msg.get("body", "").strip(),
                            "contact": chat_name,
                            "timestamp": msg.get("timestamp", 0)
                        }
                        conversation_pairs.append(pair)
                        break
        
        if conversation_pairs:
            all_conversations.extend(conversation_pairs)
            print(f"   ✅ Extraídos {len(conversation_pairs)} pares de conversação")
    
    return all_conversations

def format_for_training(conversations):
    """Formata conversas para treinamento do modelo"""
    training_data = []
    
    for conv in conversations:
        # Formato para fine-tuning do Ollama
        training_data.append({
            "prompt": conv["user_message"],
            "completion": conv["assistant_response"],
            "context": f"Conversa com {conv['contact']}"
        })
    
    return training_data

def save_training_data(data, filename="whatsapp_training_data.jsonl"):
    """Salva dados de treinamento em arquivo JSONL"""
    filepath = f"/home/homelab/myClaude/{filename}"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    print(f"✅ Dados salvos em {filepath}")
    return filepath

def create_modelfile(base_model="llama3.2", training_file="whatsapp_training_data.jsonl"):
    """Cria Modelfile para o novo modelo treinado"""
    
    modelfile_content = f'''FROM {base_model}

# Sistema de personalidade baseado nas conversas do WhatsApp
SYSTEM """
Você é Edenilson Teixeira Pascho, um profissional de TI apaixonado por tecnologia.

Características de comunicação (baseadas em conversas reais):
- Direto e objetivo nas respostas
- Usa português brasileiro natural
- Informal mas profissional
- Usa emojis ocasionalmente
- Conhecimento técnico em programação, Linux, Docker, Python
- Gosta de camping e motorhomes
- Reside em São Paulo

Responda sempre como se fosse o Edenilson conversando no WhatsApp.
"""

# Parâmetros de geração
PARAMETER temperature 0.7
PARAMETER num_ctx 4096
PARAMETER top_p 0.9
PARAMETER top_k 40
'''
    
    modelfile_path = "/home/homelab/myClaude/shared-whatsapp-trained.Modelfile"
    with open(modelfile_path, 'w', encoding='utf-8') as f:
        f.write(modelfile_content)
    
    print(f"✅ Modelfile criado: {modelfile_path}")
    return modelfile_path

def train_model_with_examples(training_data):
    """Treina o modelo usando os exemplos de conversa"""
    
    # Selecionar exemplos variados (pular os muito curtos e repetitivos)
    seen_responses = set()
    selected_examples = []
    
    for item in training_data:
        response = item['completion'].strip()
        # Pular respostas muito curtas ou já vistas
        if len(response) > 10 and response not in seen_responses:
            seen_responses.add(response)
            selected_examples.append(item)
            if len(selected_examples) >= 30:  # Máximo 30 exemplos variados
                break
    
    # Criar system prompt enriquecido com exemplos
    examples_text = "\n\nExemplos de como Edenilson responde:\n"
    
    for item in selected_examples:
        examples_text += f"\nUsuário: {item['prompt'][:150]}\n"
        examples_text += f"Edenilson: {item['completion'][:250]}\n"
    
    # Criar o system prompt completo
    system_prompt = f"""Você é Edenilson Teixeira Pascho, profissional de TI em São Paulo.

Seu estilo de comunicação:
- Direto e objetivo
- Usa português brasileiro informal
- Conhecimento em tecnologia, programação, Linux, Docker
- Interesses: camping, motorhomes, tecnologia
- Responde de forma natural como no WhatsApp
{examples_text}

Sempre responda como Edenilson responderia, mantendo o estilo casual e direto."""
    
    # Salvar Modelfile para referência
    modelfile_content = f'''FROM shared-assistant

SYSTEM """{system_prompt}"""

PARAMETER temperature 0.7
PARAMETER num_ctx 4096
'''
    
    modelfile_path = "/home/homelab/myClaude/shared-whatsapp-trained.Modelfile"
    with open(modelfile_path, 'w', encoding='utf-8') as f:
        f.write(modelfile_content)
    
    print("✅ Modelfile atualizado com exemplos de conversa")
    print(f"📄 Salvo em: {modelfile_path}")
    print(f"📊 {len(selected_examples)} exemplos variados selecionados")
    
    # Criar o modelo no Ollama via API (formato correto para versão 0.13.x)
    print("🔄 Criando modelo treinado no Ollama...")
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/create",
            json={
                "model": "shared-whatsapp",
                "from": "shared-assistant",
                "system": system_prompt
            },
            stream=True,
            timeout=300
        )
        
        if response.status_code == 200:
            print("✅ Modelo shared-whatsapp criado com sucesso!")
            for line in response.iter_lines():
                if line:
                    data = line.decode()
                    if "success" in data:
                        print("   ✅ Modelo salvo!")
            return True
        else:
            print(f"❌ Erro na API: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False



def main():
    print("=" * 60)
    print("🤖 Extração de Conversas WhatsApp para Treinamento")
    print("=" * 60)
    
    # 1. Extrair conversas
    conversations = extract_conversations()
    
    if not conversations:
        print("❌ Nenhuma conversa extraída")
        return
    
    print(f"\n📊 Total de pares de conversação: {len(conversations)}")
    
    # 2. Formatar para treinamento
    training_data = format_for_training(conversations)
    
    # 3. Salvar dados
    save_training_data(training_data)
    
    # 4. Treinar modelo
    print("\n🔄 Iniciando treinamento do modelo...")
    success = train_model_with_examples(training_data)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ TREINAMENTO CONCLUÍDO!")
        print("=" * 60)
        print("O modelo 'shared-whatsapp' foi criado com base nas suas conversas.")
        print("Para usar, atualize o whatsapp_bot.py para usar 'shared-whatsapp'")
    else:
        print("\n❌ Falha no treinamento")

if __name__ == "__main__":
    main()
