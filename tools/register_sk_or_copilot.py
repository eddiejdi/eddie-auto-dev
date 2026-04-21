#!/usr/bin/env python3
"""
Script que registra sk-or-v1 (OpenAI-compatible) como modelo disponível no GitHub Copilot Chat.

Executa via .vscode/tasks.json na ativação do workspace
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

def register_sk_or_model(vscode_user_path: Path) -> bool:
    """Registra sk-or modelo no settings.json global de VS Code"""
    
    settings_file = vscode_user_path / "settings.json"
    
    try:
        # Ler settings existente
        if settings_file.exists():
            with open(settings_file) as f:
                settings = json.load(f)
        else:
            settings = {}
        
        # Adicionar/atualizar config sk-or
        if "github.copilot.chat.customProviders" not in settings:
            settings["github.copilot.chat.customProviders"] = []
        
        providers = settings["github.copilot.chat.customProviders"]
        
        # Verificar se sk-or já existe
        sk_or_exists = any(p.get("id") == "sk-or-v1" for p in providers)
        
        if not sk_or_exists:
            providers.append({
                "id": "sk-or-v1",
                "name": "sk-or v1 (Ollama Fallback)",
                "endpoint": "http://localhost:8503/v1",
                "model": "qwen2.5-coder:1.5b",
                "capabilities": ["chat"],
                "enabled": True
            })
            
            # Escrever settings
            with open(settings_file, "w") as f:
                json.dump(settings, f, indent=2)
            
            print(f"✅ sk-or v1 registrado em {settings_file}")
            return True
        else:
            print(f"✅ sk-or v1 já registrado em {settings_file}")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao registrar sk-or: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    vscode_user = Path.home() / ".config/Code/User"
    success = register_sk_or_model(vscode_user)
    sys.exit(0 if success else 1)
