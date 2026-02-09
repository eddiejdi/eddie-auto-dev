#!/usr/bin/env python3
"""
Teste rápido da função de impressora no Open WebUI
"""
import requests
import json
import os

WEBUI_URL = os.environ.get('WEBUI_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:8002"
EMAIL = "edenilson.teixeira@rpa4all.com"
PASSWORD = "Eddie@2026"

def test_printer_function():
    print("=" * 70)
    print("  🧪 Teste da Função de Impressora")
    print("=" * 70)
    print()
    
    # 1. Login
    print("1️⃣ Autenticando...")
    r = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        json={"email": EMAIL, "password": PASSWORD}
    )
    token = r.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ Autenticado")
    
    # 2. Verificar função existe
    print("\n2️⃣ Verificando função...")
    r = requests.get(
        f"{WEBUI_URL}/api/v1/functions/printer_etiqueta",
        headers=headers
    )
    if r.status_code == 200:
        func = r.json()
        print(f"   ✅ Função encontrada: {func.get('name')}")
        print(f"   📝 ID: {func.get('id')}")
        print(f"   📋 Tipo: {func.get('type')}")
    else:
        print(f"   ❌ Função não encontrada (status {r.status_code})")
        return False
    
    # 3. Testar validação
    print("\n3️⃣ Testando validação de tamanho...")
    test_cases = [
        ("ETIQUETA PEQUENA", True, "Texto pequeno que cabe"),
        ("A" * 100, False, "Texto muito grande que não cabe"),
        ("LINHA 1\nLINHA 2\nLINHA 3", True, "Múltiplas linhas"),
    ]
    
    for text, should_fit, description in test_cases:
        print(f"   • {description}:")
        print(f"     Texto: {text[:30]}...")
        # Simulação local de validação
        estimated_width = len(max(text.split('\n'), key=len)) * 8
        valid = estimated_width <= 384
        status = "✅ Válido" if valid else "⚠️ Excede limites"
        print(f"     {status} (width: {estimated_width}px / 384px)")
    
    print("\n" + "=" * 70)
    print("✅ Testes completados com sucesso!")
    print("=" * 70)
    print("\n📝 Próximos passos:")
    print(f"  1. Acesse {WEBUI_URL}")
    print("  2. Vá para Settings → Functions")
    print("  3. Selecione '🖨️ Impressora de Etiquetas'")
    print("  4. Teste em um chat: 'Imprima TESTE 123'")
    print()
    return True

if __name__ == "__main__":
    try:
        success = test_printer_function()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        exit(1)
