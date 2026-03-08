#!/usr/bin/env python3
"""Script para atualizar modelos do Ollama com conhecimento de relatórios"""

import json
import requests

OLLAMA_HOST = "http://192.168.15.2:11434"
MODELS_DIR = "/home/homelab/myClaude"

def create_model(name: str, modelfile_path: str):
    """Cria ou atualiza um modelo no Ollama"""
    print(f"📦 Criando modelo: {name}")
    
    # Ler conteúdo do Modelfile
    with open(modelfile_path, 'r') as f:
        modelfile_content = f.read()
    
    # Enviar para Ollama
    data = {
        "name": name,
        "modelfile": modelfile_content
    }
    
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/create",
            json=data,
            stream=True,
            timeout=300
        )
        
        for line in response.iter_lines():
            if line:
                try:
                    status = json.loads(line)
                    if "status" in status:
                        print(f"  {status['status']}")
                except json.JSONDecodeError:
                    print(f"  {line.decode()}")
        
        if response.status_code == 200:
            print(f"✅ Modelo {name} criado com sucesso!\n")
            return True
        else:
            print(f"❌ Erro ao criar {name}: {response.status_code}\n")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}\n")
        return False


def main():
    print("=== Atualizando modelos Ollama ===")
    print(f"Host: {OLLAMA_HOST}\n")
    
    # Verificar se Ollama está acessível
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code != 200:
            print("❌ Ollama não está acessível")
            return
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return
    
    print("✅ Ollama acessível\n")
    
    # Atualizar modelos
    models_to_update = [
        ("shared-assistant", f"{MODELS_DIR}/shared-assistant-v2.Modelfile"),
        ("shared-whatsapp", f"{MODELS_DIR}/shared-whatsapp-v2.Modelfile"),
    ]
    
    for name, path in models_to_update:
        try:
            create_model(name, path)
        except FileNotFoundError:
            print(f"⚠️ Arquivo não encontrado: {path}\n")
    
    # Listar modelos
    print("\n=== Modelos atuais ===")
    r = requests.get(f"{OLLAMA_HOST}/api/tags")
    data = r.json()
    
    for model in data.get('models', []):
        name = model.get('name', '')
        size = model.get('size', 0) / (1024**3)
        print(f"  • {name} ({size:.1f} GB)")
    
    print("\n✅ Atualização completa!")


if __name__ == "__main__":
    main()
