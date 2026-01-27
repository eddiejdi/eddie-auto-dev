#!/usr/bin/env python3
"""Valida presença e formato das chaves obrigatórias no cofre.

Saída:
 - Código 0 quando todas as checagens passarem
 - Código >0 quando alguma falhar
"""
import sys

def main():
    errors = []
    try:
        from tools.secrets_loader import get_telegram_token, get_openwebui_api_key, get_telegram_chat_id
    except Exception as e:
        print("Erro: não foi possível importar helpers de secrets:", e)
        sys.exit(2)

    # Telegram token
    try:
        t = get_telegram_token()
        if not t or len(t) < 20:
            errors.append("Telegram token ausente ou inválido (comprimento curto)")
        else:
            print("OK: Telegram token presente (len=%d)" % len(t))
    except Exception as e:
        errors.append(f"Falha ao obter Telegram token: {e}")

    # Telegram chat id (optional but warn)
    try:
        cid = get_telegram_chat_id()
        if cid:
            print(f"OK: Telegram chat id presente: {cid}")
        else:
            print("Aviso: Telegram chat id não encontrado no cofre")
    except Exception as e:
        errors.append(f"Falha ao obter Telegram chat id: {e}")

    # OpenWebUI API key
    try:
        key = get_openwebui_api_key()
        if not key:
            errors.append("OpenWebUI API key ausente no cofre")
        else:
            # Detect common corruption: container error text
            if "OCI runtime exec failed" in key or "exec failed" in key or len(key) < 16:
                errors.append("OpenWebUI API key parece corrompida ou inválida")
            else:
                print("OK: OpenWebUI API key presente (len=%d)" % len(key))
    except Exception as e:
        errors.append(f"Falha ao obter OpenWebUI API key: {e}")

    if errors:
        print("\nErros detectados:")
        for e in errors:
            print(" -", e)
        sys.exit(3)

    print("\nTodas as checagens passaram.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
