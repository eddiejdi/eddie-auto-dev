"""
Script para gerar API Key do Open WebUI após login via Google OAuth

Como usar:
1. Faça login no Open WebUI via Google (http://192.168.15.2:3000)
2. Abra o console do navegador (F12 → Console)
3. Cole o seguinte código JavaScript:

fetch('/api/v1/auths/api_key', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  credentials: 'include'
}).then(r => r.json()).then(d => {
  console.log('API Key:', d.api_key);
  prompt('Copie sua API Key:', d.api_key);
});

4. Copie a API Key gerada
5. Cole aqui ou salve no arquivo .env como WEBUI_API_KEY

Alternativamente, vá em:
Settings (engrenagem) → Account → API Keys → Create new API key
"""

import os
import json
import urllib.request
import urllib.error

WEBUI_URL = os.getenv("WEBUI_URL", "http://192.168.15.2:3000")
API_KEY = os.getenv("WEBUI_API_KEY", "")


def test_api_key(api_key):
    """Testa se a API key é válida"""
    try:
        req = urllib.request.Request(
            f"{WEBUI_URL}/api/v1/auths/", headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return True, data
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def list_functions(api_key):
    """Lista funções instaladas"""
    try:
        req = urllib.request.Request(
            f"{WEBUI_URL}/api/v1/functions/",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def create_function(api_key, function_id, name, content, func_type="pipe"):
    """Cria uma função no Open WebUI"""
    data = json.dumps(
        {
            "id": function_id,
            "name": name,
            "type": func_type,
            "content": content,
            "meta": {"description": f"Função {name}"},
        }
    ).encode()

    try:
        req = urllib.request.Request(
            f"{WEBUI_URL}/api/v1/functions/create",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, str(e)


def toggle_function(api_key, function_id, enabled=True):
    """Ativa/desativa uma função"""
    try:
        req = urllib.request.Request(
            f"{WEBUI_URL}/api/v1/functions/id/{function_id}/toggle",
            headers={"Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, json.loads(resp.read().decode())
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("  Open WebUI - Gerenciador de Funções")
    print("=" * 60)
    print()

    # Verificar API Key
    api_key = API_KEY
    if not api_key:
        api_key = input("Cole sua API Key do Open WebUI: ").strip()

    if not api_key:
        print("\nPara obter sua API Key:")
        print("1. Acesse http://192.168.15.2:3000")
        print("2. Faça login com Google")
        print("3. Clique no seu avatar → Settings → Account")
        print("4. Em 'API Keys', clique em 'Create new secret key'")
        print("5. Copie a chave e cole aqui ou salve em WEBUI_API_KEY no .env")
        return

    # Testar API Key
    print("Testando API Key...")
    valid, result = test_api_key(api_key)

    if not valid:
        print(f"API Key invalida: {result}")
        return

    print(f"API Key valida! Usuario: {result.get('email', '?')}")

    # Listar funções
    print("\nFuncoes instaladas:")
    functions = list_functions(api_key)
    if isinstance(functions, list):
        if functions:
            for f in functions:
                status = "ON" if f.get("is_active") else "OFF"
                print(f"  [{status}] {f.get('id')}: {f.get('name')}")
        else:
            print("  Nenhuma funcao instalada")
    else:
        print(f"  Erro: {functions}")

    # Instalar Agent Coordinator
    print("\nInstalar Agent Coordinator? (s/n): ", end="")
    choice = input().strip().lower()

    if choice == "s":
        function_file = "/home/homelab/myClaude/openwebui_agent_coordinator_function.py"
        try:
            with open(function_file, "r") as f:
                content = f.read()
        except FileNotFoundError:
            # Tentar caminho alternativo
            import pathlib

            alt_path = (
                pathlib.Path(__file__).parent
                / "openwebui_agent_coordinator_function.py"
            )
            with open(alt_path, "r") as f:
                content = f.read()

        print("Instalando Agent Coordinator...")
        success, result = create_function(
            api_key, "agent_coordinator", "Agent Coordinator", content, "pipe"
        )

        if success:
            print("Funcao instalada com sucesso!")
            print(f"  ID: {result.get('id')}")

            # Ativar
            print("Ativando funcao...")
            toggle_function(api_key, "agent_coordinator", True)
            print("Funcao ativada!")
        else:
            print(f"Erro ao instalar: {result}")

    print("\nConcluido!")


if __name__ == "__main__":
    main()
