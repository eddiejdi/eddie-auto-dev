#!/usr/bin/env python3
"""Instala a função OCR Inteligente no Open WebUI via API.

Uso:
    python3 install_ocr_function.py
    WEBUI_EMAIL=admin@example.com WEBUI_PASS=xxx python3 install_ocr_function.py
"""

import sys
import os
import json
import urllib.request
import urllib.error
import getpass
import pathlib

WEBUI_URL = os.environ.get("WEBUI_URL", "http://localhost:3000")
FUNCTION_FILE = pathlib.Path(__file__).parent / "ocr_inteligente.py"


def signin(email: str, credential: str) -> str:
    payload = json.dumps({"email": email, "password": credential}).encode()
    req = urllib.request.Request(
        f"{WEBUI_URL}/api/v1/auths/signin",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["token"]


def upsert_function(token: str, code: str) -> dict:
    meta = {
        "description": (
            "Extrai e interpreta texto de imagens com modelos de visão locais (Ollama). "
            "Pipeline 2 estágios: visão + LLM. Roda 100% local."
        ),
        "manifest": {},
    }
    payload = json.dumps({
        "id": "ocr_inteligente",
        "name": "🔍 OCR Inteligente",
        "content": code,
        "meta": meta,
    }).encode()

    # Tenta criar primeiro; se existir, atualiza via POST no endpoint de update
    for method, url in [
        ("POST", f"{WEBUI_URL}/api/v1/functions/create"),
        ("POST", f"{WEBUI_URL}/api/v1/functions/id/ocr_inteligente/update"),
    ]:
        req = urllib.request.Request(
            url, data=payload, method=method,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code in (400, 409) and ("exist" in body.lower() or "duplicate" in body.lower()):
                continue  # tenta o próximo endpoint (update)
            raise RuntimeError(f"HTTP {e.code}: {body}") from e

    raise RuntimeError("Não foi possível criar nem atualizar a função.")


def update_valves(token: str, valves: dict) -> None:
    """Atualiza os valves globais da função no Open WebUI."""
    payload = json.dumps(valves).encode()
    for url in [
        f"{WEBUI_URL}/api/v1/functions/id/ocr_inteligente/valves/update",
        f"{WEBUI_URL}/api/v1/functions/id/ocr_inteligente/valves",
    ]:
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
                return
        except urllib.error.HTTPError:
            continue
    print("      ⚠️  Valve update não suportado nesta versão — ajuste manualmente se necessário.")


def main() -> None:
    print("=== Instalador — OCR Inteligente (Open WebUI) ===\n")

    email = os.environ.get("WEBUI_EMAIL") or input("Email admin Open WebUI: ").strip()
    cred = os.environ.get("WEBUI_PASS") or getpass.getpass("Credencial: ")

    print("\n[1/3] Autenticando...")
    try:
        token = signin(email, cred)
        print(f"      ✅ Autenticado ({token[:12]}...)")
    except Exception as exc:
        print(f"      ❌ Falha: {exc}")
        sys.exit(1)

    print("[2/3] Lendo código da função...")
    code = FUNCTION_FILE.read_text()
    print(f"      ✅ {len(code)} bytes")

    print("[3/3] Publicando no Open WebUI...")
    try:
        result = upsert_function(token, code)
        print(f"      ✅ id={result.get('id', '?')}  name={result.get('name', '?')}")
    except Exception as exc:
        print(f"      ❌ Erro: {exc}")
        sys.exit(1)

    ollama_host = os.environ.get("OLLAMA_HOST_OVERRIDE", "http://192.168.15.2:11437")
    print(f"[4/4] Atualizando valve OLLAMA_HOST → {ollama_host} ...")
    update_valves(token, {"OLLAMA_HOST": ollama_host})
    print("      ✅ Valve atualizado.")

    print(f"\n🎉 Pronto! Acesse {WEBUI_URL} → seletor de modelos → '🔍 OCR Inteligente'")


if __name__ == "__main__":
    main()
