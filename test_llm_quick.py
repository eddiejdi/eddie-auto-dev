#!/usr/bin/env python3
"""
Teste rápido de geração de código com LLM
"""
import httpx
import json
import sys

OLLAMA_URL = "http://192.168.15.2:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:1.5b"

prompt = """Implemente uma classe Calculator em Python com os seguintes métodos:
- add(a, b): soma dois números
- subtract(a, b): subtrai dois números
- multiply(a, b): multiplica dois números
- divide(a, b): divide dois números (com tratamento de divisão por zero)
- power(a, b): potenciação
- sqrt(a): raiz quadrada

Inclua também:
- Atributo history para armazenar histórico de operações
- Atributo memory para armazenar um valor

Retorne APENAS o código Python, sem explicações."""

system = """Você é um programador Python expert. Suas respostas devem conter APENAS código Python funcional, sem explicações.

REGRAS:
1. Retorne APENAS código Python válido
2. NÃO use blocos markdown
3. O código deve ser executável imediatamente"""

print(f"[*] Usando modelo: {MODEL}")
print(f"[*] Gerando código...")

try:
    with httpx.Client(timeout=120) as client:
        response = client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 4096
                }
            }
        )
        response.raise_for_status()
        result = response.json()
        code = result.get("response", "")
        
        print("\n" + "="*60)
        print("CÓDIGO GERADO:")
        print("="*60)
        print(code)
        print("="*60)
        
        # Salvar
        with open("/tmp/calculator_test.py", "w") as f:
            # Limpar código de markdown
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]
            elif "```" in code:
                code = code.split("```")[1].split("```")[0]
            f.write(code.strip())
        
        print(f"\n[OK] Código salvo em /tmp/calculator_test.py")
        
except Exception as e:
    print(f"[ERRO] {e}")
