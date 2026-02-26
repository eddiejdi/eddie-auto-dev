#!/usr/bin/env python3
"""
Inventário de MCP Servers disponíveis no Homelab
Identifica todos os servidores MCP, suas ferramentas e configurações
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

HOMELAB_HOST = "homelab@192.168.15.2"
HOMELAB_BASE = "/home/homelab/eddie-auto-dev"

# MCP Servers conhecidos no homelab
MCP_SERVERS = {
    "github": {
        "path": f"{HOMELAB_BASE}/github-mcp-server/src/github_mcp_server.py",
        "description": "GitHub MCP Server - 35+ ferramentas para integração com GitHub",
        "category": "development",
        "transport": "stdio",
    },
    "ssh-agent": {
        "path": f"{HOMELAB_BASE}/ssh_agent_mcp.py",
        "description": "SSH Agent MCP - Execução de comandos SSH remotos",
        "category": "infrastructure",
        "transport": "stdio",
    },
    "rag": {
        "path": f"{HOMELAB_BASE}/rag-mcp-server/src/rag_mcp_server.py",
        "description": "RAG MCP Server - Retrieval Augmented Generation",
        "category": "ai",
        "transport": "stdio",
    },
    "homelab": {
        "path": "/home/homelab/estou-aqui-deploy/scripts/homelab_mcp_server.py",
        "description": "Homelab MCP Server - Gerenciamento do servidor homelab",
        "category": "infrastructure",
        "transport": "stdio",
    },
}


def run_ssh_command(command: str) -> tuple[int, str, str]:
    """Executa comando via SSH no homelab"""
    try:
        result = subprocess.run(
            ["ssh", HOMELAB_HOST, command],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Timeout"
    except Exception as e:
        return 1, "", str(e)


def check_mcp_server(name: str, info: Dict[str, str]) -> Dict[str, Any]:
    """Verifica status e informações de um MCP server"""
    path = info["path"]

    # Verifica se arquivo existe
    returncode, stdout, stderr = run_ssh_command(f"test -f {path} && echo 'exists' || echo 'not_found'")

    exists = stdout.strip() == "exists"

    result = {
        "name": name,
        "path": path,
        "description": info["description"],
        "category": info["category"],
        "transport": info["transport"],
        "exists": exists,
        "executable": False,
        "tools_count": 0,
        "dependencies_ok": False,
    }

    if not exists:
        return result

    # Verifica se é executável
    returncode, stdout, stderr = run_ssh_command(f"test -x {path} && echo 'yes' || echo 'no'")
    result["executable"] = stdout.strip() == "yes"

    # Tenta extrair informações do servidor (se possível)
    # Para GitHub MCP: contar ferramentas via grep
    if "github" in name:
        returncode, stdout, stderr = run_ssh_command(
            f"grep -c 'def tool_' {path} 2>/dev/null || echo 0"
        )
        try:
            result["tools_count"] = int(stdout.strip())
        except:
            result["tools_count"] = 0

    return result


def check_python_deps() -> Dict[str, bool]:
    """Verifica dependências Python necessárias no homelab"""
    deps = ["mcp", "httpx", "paramiko", "chromadb"]
    results = {}

    for dep in deps:
        returncode, stdout, stderr = run_ssh_command(
            f"python3 -c 'import {dep}' 2>/dev/null && echo 'ok' || echo 'missing'"
        )
        results[dep] = stdout.strip() == "ok"

    return results


def generate_pycharm_config(servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Gera configuração para PyCharm baseada nos servidores disponíveis"""
    config = {
        "version": "1.0",
        "mcp_servers": {},
        "ssh_config": {
            "host": "192.168.15.2",
            "user": "homelab",
            "key_file": "~/.ssh/id_rsa",
        },
    }

    for server in servers:
        if server["exists"]:
            config["mcp_servers"][server["name"]] = {
                "command": "ssh",
                "args": [
                    f"{HOMELAB_HOST}",
                    "python3",
                    server["path"],
                ],
                "transport": server["transport"],
                "description": server["description"],
                "category": server["category"],
            }

    return config


def main():
    print("=" * 70)
    print("🔍 INVENTÁRIO DE MCP SERVERS NO HOMELAB")
    print("=" * 70)
    print()

    # Verificar conectividade SSH
    print("📡 Verificando conectividade com homelab...")
    returncode, stdout, stderr = run_ssh_command("echo 'connected'")
    if returncode != 0 or stdout.strip() != "connected":
        print("❌ Falha ao conectar com homelab!")
        print(f"   Error: {stderr}")
        sys.exit(1)
    print("✅ Conexão OK\n")

    # Verificar dependências Python
    print("🐍 Verificando dependências Python...")
    deps = check_python_deps()
    for dep, ok in deps.items():
        status = "✅" if ok else "❌"
        print(f"   {status} {dep}")
    print()

    # Inventariar MCP servers
    print("🔎 Inventariando MCP servers...")
    servers = []
    for name, info in MCP_SERVERS.items():
        result = check_mcp_server(name, info)
        servers.append(result)

        status = "✅" if result["exists"] else "❌"
        print(f"\n{status} {result['name'].upper()}")
        print(f"   Descrição: {result['description']}")
        print(f"   Path: {result['path']}")
        print(f"   Categoria: {result['category']}")
        print(f"   Existe: {result['exists']}")
        if result["exists"]:
            print(f"   Executável: {result['executable']}")
            if result["tools_count"] > 0:
                print(f"   Ferramentas: {result['tools_count']}")

    print("\n" + "=" * 70)
    print("📊 RESUMO")
    print("=" * 70)

    total = len(servers)
    available = sum(1 for s in servers if s["exists"])

    print(f"Total de servidores configurados: {total}")
    print(f"Servidores disponíveis: {available}")
    print(f"Servidores indisponíveis: {total - available}")

    # Gerar configuração PyCharm
    print("\n" + "=" * 70)
    print("⚙️  GERANDO CONFIGURAÇÃO PYCHARM")
    print("=" * 70)

    config = generate_pycharm_config(servers)

    # Salvar configuração
    output_dir = Path(__file__).parent.parent / ".idea"
    output_dir.mkdir(exist_ok=True)

    config_file = output_dir / "mcp-servers.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Configuração salva em: {config_file}")
    print(f"\n📋 Conteúdo:\n")
    print(json.dumps(config, indent=2))

    # Criar também versão para home do usuário
    home_config = Path.home() / ".config" / "JetBrains" / "eddie-mcp-servers.json"
    home_config.parent.mkdir(parents=True, exist_ok=True)
    with open(home_config, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Cópia salva em: {home_config}")

    print("\n" + "=" * 70)
    print("✨ INVENTÁRIO COMPLETO!")
    print("=" * 70)


if __name__ == "__main__":
    main()

