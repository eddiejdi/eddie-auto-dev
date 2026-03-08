#!/usr/bin/env python3
"""
Instala a Function GitHub Copilot no Open WebUI via API Key
"""
import os
from pathlib import Path
import requests
from tools.secrets_loader import get_openwebui_api_key

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3000")
FUNCTION_ID = "github_copilot"
FUNCTION_NAME = "GitHub Copilot CLI"
FUNCTION_DESC = "Executa comandos do GitHub Copilot via gh copilot"


def load_tool_code() -> str:
    tool_path = Path(__file__).parent / "openwebui_copilot_tool.py"
    return tool_path.read_text(encoding="utf-8")


def get_token() -> str:
    try:
        return get_openwebui_api_key()
    except Exception:
        token_path = Path.home() / ".openwebui_token"
        if token_path.exists():
            return token_path.read_text(encoding="utf-8").strip()
        return ""


def upsert_function(token: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    content = load_tool_code()

    resp = requests.get(
        f"{OPENWEBUI_URL}/api/v1/functions/{FUNCTION_ID}",
        headers=headers,
        timeout=15,
    )

    payload = {
        "id": FUNCTION_ID,
        "name": FUNCTION_NAME,
        "meta": {"description": FUNCTION_DESC},
        "content": content,
        "is_active": True,
        "is_global": True,
    }

    if resp.status_code == 200:
        resp = requests.post(
            f"{OPENWEBUI_URL}/api/v1/functions/{FUNCTION_ID}/update",
            headers=headers,
            json=payload,
            timeout=30,
        )
    else:
        resp = requests.post(
            f"{OPENWEBUI_URL}/api/v1/functions/create",
            headers=headers,
            json=payload,
            timeout=30,
        )

    if resp.status_code in (200, 201):
        print("✅ Function 'github_copilot' instalada/atualizada com sucesso!")
        return True

    print(f"❌ Erro ao instalar function: {resp.status_code} - {resp.text}")
    return False


def main() -> None:
    print("=" * 55)
    print("🔧 Instalador de Function GitHub Copilot - Open WebUI")
    print("=" * 55)
    print(f"URL: {OPENWEBUI_URL}")

    token = get_token()
    if not token:
        print("❌ WEBUI API key não encontrada no cofre nem em ~/.openwebui_token.")
        print("Adicione 'openwebui/api_key' ao cofre e tente novamente.")
        raise SystemExit(1)

    upsert_function(token)


if __name__ == "__main__":
    main()
