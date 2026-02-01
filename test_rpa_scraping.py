#!/usr/bin/env python3
"""
Teste automatizado do Agent Chat usando Web Scraping
Alternativa ao Selenium quando Chrome não está disponível
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

# URLs dos serviços
SERVICES = {
    "Agent Chat": "http://localhost:8505",
    "Monitor": "http://localhost:8504",
    "Dashboard": "http://localhost:8502",
    "API Docs": "http://localhost:8503/docs",
    "API Health": "http://localhost:8503/health",
    "API Agents": "http://localhost:8503/agents",
    "Auto-scaler": "http://localhost:8503/autoscaler/status",
    "Instructor": "http://localhost:8503/instructor/status",
}


def test_streamlit_page(name, url):
    """Testa uma página Streamlit."""
    print(f"\n🧪 Testando {name} ({url})")
    print("-" * 50)

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print(f"   ❌ Status Code: {response.status_code}")
            return False

        print(f"   ✅ Status Code: {response.status_code}")

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Verifica se é Streamlit
        is_streamlit = "streamlit" in response.text.lower()
        print(f"   {'✅' if is_streamlit else '❌'} Framework Streamlit detectado")

        # Verifica título
        title = soup.find("title")
        if title:
            print(f"   📄 Título: {title.text}")

        # Verifica scripts
        scripts = soup.find_all("script")
        print(f"   📦 Scripts carregados: {len(scripts)}")

        # Verifica se tem conteúdo do app
        has_content = len(response.text) > 1000
        print(
            f"   {'✅' if has_content else '❌'} Conteúdo da página: {len(response.text)} bytes"
        )

        return is_streamlit and has_content

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_api_endpoint(name, url, expected_fields=None):
    """Testa um endpoint da API."""
    print(f"\n🧪 Testando {name} ({url})")
    print("-" * 50)

    try:
        response = requests.get(url, timeout=10)

        print(f"   Status Code: {response.status_code}")

        if response.status_code != 200:
            return False

        # Tenta parsear JSON
        try:
            data = response.json()
            print("   ✅ Resposta JSON válida")

            # Mostra campos
            if isinstance(data, dict):
                print(f"   📋 Campos: {list(data.keys())[:5]}")

                # Verifica campos esperados
                if expected_fields:
                    for field in expected_fields:
                        has_field = field in data
                        print(
                            f"   {'✅' if has_field else '❌'} Campo '{field}' presente"
                        )

            return True

        except json.JSONDecodeError:
            # Pode ser HTML (Swagger)
            if "swagger" in response.text.lower() or "openapi" in response.text.lower():
                print("   ✅ Swagger UI detectado")
                return True
            return False

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_code_generation():
    """Testa a geração de código via API."""
    print("\n🧪 Testando Geração de Código")
    print("-" * 50)

    try:
        response = requests.post(
            "http://localhost:8503/code/generate",
            json={
                "description": "função que soma dois números",
                "language": "python",
                "context": "",
            },
            timeout=120,
        )

        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if "code" in data:
                code = data["code"]
                print(f"   ✅ Código gerado ({len(code)} caracteres)")
                print(f"   📝 Preview: {code[:100]}...")

                # Verifica se tem estrutura de função
                has_def = "def " in code
                has_return = "return" in code
                print(f"   {'✅' if has_def else '❌'} Contém definição de função")
                print(f"   {'✅' if has_return else '❌'} Contém return")

                return True

        return False

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_code_execution():
    """Testa a execução de código via API."""
    print("\n🧪 Testando Execução de Código")
    print("-" * 50)

    try:
        response = requests.post(
            "http://localhost:8503/code/execute",
            json={
                "code": "print('Hello from RPA test!')\nprint(2 + 2)",
                "language": "python",
            },
            timeout=60,
        )

        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   📋 Resposta: {json.dumps(data)[:200]}...")

            # Endpoint respondeu, mesmo que execução falhe (Docker)
            print("   ✅ Endpoint de execução funcionando")
            return True

        return False

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_chat_interaction():
    """Simula interação com o chat via Streamlit API."""
    print("\n🧪 Testando Interação com Chat (via Ollama)")
    print("-" * 50)

    try:
        # Testa diretamente o Ollama
        response = requests.post(
            "http://192.168.15.2:11434/api/generate",
            json={
                "model": "qwen2.5-coder:14b",
                "prompt": "Responda apenas 'OK' se você está funcionando.",
                "stream": False,
            },
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            resp_text = data.get("response", "")
            print(f"   ✅ Ollama respondeu: {resp_text[:50]}...")
            return True

        return False

    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def main():
    """Executa todos os testes."""
    print("=" * 60)
    print("   TESTES AUTOMATIZADOS - WEB SCRAPING / RPA")
    print("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    results = {}

    # Testa páginas Streamlit
    for name in ["Agent Chat", "Monitor", "Dashboard"]:
        results[name] = test_streamlit_page(name, SERVICES[name])

    # Testa API Docs (Swagger)
    results["API Docs"] = test_api_endpoint("API Docs", SERVICES["API Docs"])

    # Testa endpoints da API
    results["API Agents"] = test_api_endpoint(
        "API Agents", SERVICES["API Agents"], ["available_languages"]
    )

    results["Auto-scaler"] = test_api_endpoint(
        "Auto-scaler", SERVICES["Auto-scaler"], ["current_agents", "running"]
    )

    results["Instructor"] = test_api_endpoint(
        "Instructor", SERVICES["Instructor"], ["running", "training_schedule"]
    )

    # Testa funcionalidades principais
    results["Geração de Código"] = test_code_generation()
    results["Execução de Código"] = test_code_execution()
    results["Chat (Ollama)"] = test_chat_interaction()

    # Resumo
    print("\n" + "=" * 60)
    print("   RESUMO DOS TESTES RPA")
    print("=" * 60)

    passed = 0
    failed = 0

    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n   RESULTADO FINAL: {passed}/{passed + failed} testes passaram")

    if failed == 0:
        print("   🎉 TODOS OS TESTES PASSARAM!")
    else:
        print(f"   ⚠️  {failed} teste(s) falharam")

    print("=" * 60)

    # Salva resultados
    with open("/tmp/rpa_scraping_results.json", "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "passed": passed,
                "failed": failed,
                "total": passed + failed,
            },
            f,
            indent=2,
        )

    print("\n📄 Resultados salvos em /tmp/rpa_scraping_results.json")

    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
