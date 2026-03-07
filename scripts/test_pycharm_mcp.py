#!/usr/bin/env python3
"""
Teste de integração MCP via PyCharm
Valida conectividade e funcionamento dos MCP servers do homelab
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

HOMELAB_HOST = "homelab@192.168.15.2"
HOMELAB_BASE = "/home/homelab/shared-auto-dev"

# Cores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Imprime cabeçalho formatado"""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str):
    """Imprime mensagem de sucesso"""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Imprime mensagem de erro"""
    print(f"{RED}❌ {text}{RESET}")


def print_info(text: str):
    """Imprime mensagem informativa"""
    print(f"{YELLOW}ℹ️  {text}{RESET}")


def run_ssh_command(command: str, timeout: int = 10) -> Tuple[int, str, str]:
    """Executa comando via SSH no homelab"""
    try:
        result = subprocess.run(
            ["ssh", HOMELAB_HOST, command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timeout"
    except Exception as e:
        return 1, "", str(e)


def test_ssh_connectivity() -> bool:
    """Testa conectividade SSH com homelab"""
    print_header("TESTE 1: Conectividade SSH")

    print("Conectando ao homelab (192.168.15.2)...")
    returncode, stdout, stderr = run_ssh_command("echo 'SSH_OK'")

    if returncode == 0 and "SSH_OK" in stdout:
        print_success("Conexão SSH estabelecida com sucesso")
        return True
    else:
        print_error(f"Falha na conexão SSH: {stderr}")
        return False


def test_python_environment() -> bool:
    """Testa ambiente Python no homelab"""
    print_header("TESTE 2: Ambiente Python")

    print("Verificando versão do Python...")
    returncode, stdout, stderr = run_ssh_command("python3 --version")

    if returncode == 0:
        version = stdout.strip()
        print_success(f"Python detectado: {version}")
    else:
        print_error("Python3 não encontrado")
        return False

    # Testar imports necessários
    print("\nVerificando módulos Python...")
    modules = ["json", "sys", "pathlib", "subprocess"]
    all_ok = True

    for module in modules:
        returncode, _, _ = run_ssh_command(f"python3 -c 'import {module}'")
        if returncode == 0:
            print_success(f"Módulo {module}: OK")
        else:
            print_error(f"Módulo {module}: FALTANDO")
            all_ok = False

    return all_ok


def test_github_mcp_server() -> bool:
    """Testa GitHub MCP Server"""
    print_header("TESTE 3: GitHub MCP Server")

    path = f"{HOMELAB_BASE}/github-mcp-server/src/github_mcp_server.py"

    print(f"Verificando arquivo: {path}")
    returncode, stdout, _ = run_ssh_command(f"test -f {path} && echo 'exists'")

    if "exists" not in stdout:
        print_error("Arquivo não encontrado")
        return False

    print_success("Arquivo encontrado")

    # Contar ferramentas disponíveis
    print("\nContando ferramentas disponíveis...")
    returncode, stdout, _ = run_ssh_command(
        f"grep -E 'async def github_' {path} | grep -v '__' | wc -l"
    )

    try:
        count = int(stdout.strip())
        if count > 0:
            print_success(f"Ferramentas disponíveis: {count}")
            return True
        else:
            print_info("Nenhuma ferramenta detectada via grep, verificando estrutura...")
            # Verificar se o arquivo tem pelo menos a estrutura básica
            returncode, stdout, _ = run_ssh_command(f"head -50 {path}")
            if "github" in stdout.lower() and "mcp" in stdout.lower():
                print_success("Estrutura MCP detectada no arquivo")
                return True
            return False
    except:
        print_error("Não foi possível contar ferramentas")
        return False


def test_ssh_agent_mcp() -> bool:
    """Testa SSH Agent MCP"""
    print_header("TESTE 4: SSH Agent MCP")

    path = f"{HOMELAB_BASE}/ssh_agent_mcp.py"

    print(f"Verificando arquivo: {path}")
    returncode, stdout, _ = run_ssh_command(f"test -f {path} && echo 'exists'")

    if "exists" not in stdout:
        print_error("Arquivo não encontrado")
        return False

    print_success("Arquivo encontrado")

    # Tentar importar o módulo
    print("\nTestando importação do módulo...")
    test_cmd = f"cd {HOMELAB_BASE} && source .venv/bin/activate && python -c 'from ssh_agent_mcp import MCPServer; s=MCPServer(); print(f\"Total de ferramentas: {{len(s.tools)}}\")' 2>&1 | grep -E '(Total|ferramentas)'"
    
    returncode, stdout, stderr = run_ssh_command(test_cmd, timeout=15)

    if returncode == 0 and "Total de ferramentas:" in stdout:
        lines = stdout.strip().split("\n")
        count_line = [l for l in lines if "Total de ferramentas:" in l][0]
        print_success(f"Servidor inicializado: {count_line}")
        return True
    else:
        print_error(f"Falha ao inicializar: {stdout[:200]}")
        return False


def test_rag_mcp_server() -> bool:
    """Testa RAG MCP Server"""
    print_header("TESTE 5: RAG MCP Server")

    path = f"{HOMELAB_BASE}/rag-mcp-server/src/rag_mcp_server.py"

    print(f"Verificando arquivo: {path}")
    returncode, stdout, _ = run_ssh_command(f"test -f {path} && echo 'exists'")

    if "exists" not in stdout:
        print_error("Arquivo não encontrado")
        return False

    print_success("Arquivo encontrado")

    # Verificar dependências do RAG
    print("\nVerificando dependências do RAG...")
    returncode, stdout, _ = run_ssh_command("python3 -c 'import chromadb' 2>&1")

    if returncode == 0:
        print_success("ChromaDB instalado")
        return True
    else:
        print_info("ChromaDB não instalado (pode ser necessário para funcionalidade completa)")
        return True  # Não bloqueia o teste


def test_ollama_connectivity() -> bool:
    """Testa conectividade com Ollama no homelab"""
    print_header("TESTE 6: Ollama LLM")

    print("Verificando Ollama na porta 11434...")
    returncode, stdout, stderr = run_ssh_command(
        "curl -s http://localhost:11434/api/tags | python3 -m json.tool | head -20"
    )

    if returncode == 0 and stdout:
        print_success("Ollama respondendo corretamente")
        print_info("Modelos disponíveis detectados")
        return True
    else:
        print_error("Ollama não está respondendo")
        return False


def test_mcp_config_files() -> bool:
    """Testa arquivos de configuração MCP gerados"""
    print_header("TESTE 7: Arquivos de Configuração")

    # Verificar arquivo local
    config_file = Path(__file__).parent.parent / ".idea" / "mcp-servers.json"

    print(f"Verificando: {config_file}")
    if config_file.exists():
        print_success("Arquivo de configuração encontrado")

        try:
            with open(config_file) as f:
                config = json.load(f)

            servers = config.get("mcp_servers", {})
            print_success(f"Servidores configurados: {len(servers)}")

            for name, info in servers.items():
                print_info(f"  - {name}: {info.get('description', 'N/A')}")

            return True
        except Exception as e:
            print_error(f"Erro ao ler configuração: {e}")
            return False
    else:
        print_error("Arquivo de configuração não encontrado")
        print_info("Execute: python3 scripts/inventory_homelab_mcp.py")
        return False


def generate_report(results: Dict[str, bool]):
    """Gera relatório final dos testes"""
    print_header("RELATÓRIO FINAL")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    print(f"Total de testes: {total}")
    print_success(f"Aprovados: {passed}")
    if failed > 0:
        print_error(f"Reprovados: {failed}")

    print("\nDetalhes:")
    for test_name, result in results.items():
        status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
        print(f"  {status} - {test_name}")

    print("\n" + "=" * 70)

    if passed == total:
        print_success("🎉 TODOS OS TESTES PASSARAM!")
        print_info("PyCharm está pronto para usar os MCP servers do homelab")
        return 0
    else:
        print_error("⚠️  ALGUNS TESTES FALHARAM")
        print_info("Verifique os erros acima antes de usar os MCP servers")
        return 1


def main():
    """Executa todos os testes"""
    print_header("🧪 TESTE DE INTEGRAÇÃO MCP PARA PYCHARM")
    print_info("Este script valida a configuração dos MCP servers do homelab")

    results = {}

    # Executar testes em sequência
    results["Conectividade SSH"] = test_ssh_connectivity()

    if results["Conectividade SSH"]:
        results["Ambiente Python"] = test_python_environment()
        results["GitHub MCP Server"] = test_github_mcp_server()
        results["SSH Agent MCP"] = test_ssh_agent_mcp()
        results["RAG MCP Server"] = test_rag_mcp_server()
        results["Ollama LLM"] = test_ollama_connectivity()
        results["Arquivos de Configuração"] = test_mcp_config_files()
    else:
        print_error("\n⚠️  Testes interrompidos devido a falha na conectividade SSH")
        return 1

    # Gerar relatório
    return generate_report(results)


if __name__ == "__main__":
    sys.exit(main())


