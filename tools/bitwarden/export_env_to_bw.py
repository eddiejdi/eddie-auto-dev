#!/usr/bin/env python3
"""
Export secrets from .env files to Bitwarden-compatible JSON format.
This can be imported manually into Bitwarden Web Vault or via CLI.
"""

import sys
import json
from pathlib import Path

def env_to_bw_json(env_file):
    """Convert .env file to Bitwarden Secure Notes JSON format."""
    env_file = Path(env_file).expanduser()
    if not env_file.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {env_file}")
    
    items = []
    file_name = env_file.name
    
    with open(env_file, "r") as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if "=" not in line:
            name = f"{file_name}:line"
            value = line
        else:
            key, val = line.split("=", 1)
            name = f"{file_name}:{key.strip()}"
            value = val.strip()
        
        # Secure Note format for Bitwarden
        item = {
            "type": 3,  # Secure Note
            "name": name,
            "notes": value,
            "secureNote": {
                "type": 0  # General note
            }
        }
        items.append(item)
    
    return items

if __name__ == "__main__":
    try:
        env_file = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / ".secrets" / ".env.jira")
        items = env_to_bw_json(env_file)
        
        output_file = Path(env_file).stem + "_bitwarden.json"
        with open(output_file, "w") as f:
            json.dump(items, f, indent=2)
        
        print(f"✓ Exportado para {output_file}")
        print(f"  Items: {len(items)}")
        print("\nProximos passos:")
        print("  1. Abra https://vault.bitwarden.com")
        print("  2. Vá em Settings → Import Data")
        print(f"  3. Use 'Bitwarden (json)' e selecione {output_file}")
        print("  4. Clique Import")
        
        sys.exit(0)
    except Exception as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
