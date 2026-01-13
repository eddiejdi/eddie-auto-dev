#!/usr/bin/env python3
"""
Script de teste para API de geração de código
"""
import requests
import json

BASE_URL = "http://localhost:8503"

def test_code_generate():
    """Testa o endpoint /code/generate"""
    print("=== Teste de Geração de Código ===\n")
    
    data = {
        "language": "python",
        "requirements": "soma dois numeros",
        "description": "funcao simples para somar dois numeros"
    }
    
    print(f"Request: {json.dumps(data, indent=2)}")
    
    try:
        r = requests.post(
            f"{BASE_URL}/code/generate",
            json=data,
            timeout=120
        )
        print(f"\nStatus: {r.status_code}")
        
        if r.status_code == 200:
            result = r.json()
            print(f"Success: {result.get('success', False)}")
            if 'code' in result:
                print(f"\nCódigo gerado:\n{result['code'][:500]}...")
            if 'tests' in result:
                print(f"\nTestes gerados:\n{result['tests'][:300]}...")
        else:
            print(f"Error: {r.text[:500]}")
            
    except Exception as e:
        print(f"Exception: {e}")

def test_communication_after():
    """Verifica se mensagens foram registradas no bus"""
    print("\n=== Verificando Communication Bus ===\n")
    
    r = requests.get(f"{BASE_URL}/communication/stats", timeout=10)
    stats = r.json()
    print(f"Total mensagens: {stats['total_messages']}")
    print(f"Por tipo: {stats['by_type']}")
    
    # Últimas 3 mensagens
    r = requests.get(f"{BASE_URL}/communication/messages?limit=3", timeout=10)
    data = r.json()
    print(f"\nÚltimas mensagens:")
    for msg in data.get('messages', [])[-3:]:
        print(f"  [{msg['type']}] {msg['source']} -> {msg['target']}: {msg['content'][:50]}...")

if __name__ == "__main__":
    test_code_generate()
    test_communication_after()
