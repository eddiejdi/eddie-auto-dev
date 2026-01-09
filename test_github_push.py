#!/usr/bin/env python3
"""Testa push do projeto para GitHub"""
import asyncio
import os
import sys

# Setup path
sys.path.insert(0, "/home/eddie/myClaude")
# GITHUB_TOKEN deve ser definido via variável de ambiente
if not os.environ.get("GITHUB_TOKEN"):
    print("ERRO: GITHUB_TOKEN não definido")
    sys.exit(1)

from specialized_agents.github_client import DirectGitHubClient


async def main():
    print("=" * 50)
    print("Teste de Push para GitHub")
    print("=" * 50)
    
    client = DirectGitHubClient()
    print(f"Token: {client.token[:15]}...")
    
    # Testar conexão
    connected = await client.check_connection()
    print(f"Conectado ao GitHub: {connected}")
    
    if not connected:
        print("ERRO: Token inválido ou sem conexão")
        return
    
    # Obter usuário
    user = await client.get_user()
    print(f"Usuário: {user.get('login', 'N/A')}")
    
    # Verificar se projeto existe
    project_path = "/home/eddie/myClaude/dev_projects/python/calculadora_final"
    
    if not os.path.exists(project_path):
        print(f"ERRO: Projeto não encontrado em {project_path}")
        # Listar projetos disponíveis
        base = "/home/eddie/myClaude/dev_projects/python"
        if os.path.exists(base):
            print(f"\nProjetos disponíveis em {base}:")
            for item in os.listdir(base):
                print(f"  - {item}")
        return
    
    # Listar arquivos do projeto
    print(f"\nArquivos em {project_path}:")
    for item in os.listdir(project_path):
        print(f"  - {item}")
    
    # Push
    print("\nFazendo push para GitHub...")
    result = await client.push_project(
        project_path,
        "calculadora-python",
        "Calculadora CLI em Python - criada por Specialized Agent"
    )
    
    print(f"\nResultado: {result}")
    
    if result.get("success"):
        print("\n" + "=" * 50)
        print(f"🔗 LINK DO PROJETO: {result.get('url')}")
        print("=" * 50)
    else:
        print(f"\nERRO: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
