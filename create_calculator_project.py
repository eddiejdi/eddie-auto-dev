#!/usr/bin/env python3
"""
Script para criar projeto de calculadora usando o fluxo completo:
Analista de Requisitos -> Programador -> Revisão -> GitHub
"""

import asyncio
import sys

sys.path.insert(0, "/home/homelab/myClaude")

from specialized_agents import AgentManager
from specialized_agents.github_client import GitHubAgentClient


async def create_calculator_project():
    """Executa o fluxo completo de criação da calculadora"""

    print("=" * 60)
    print("🚀 INICIANDO CRIAÇÃO DO PROJETO CALCULADORA")
    print("=" * 60)

    # Descrição do projeto
    project_description = """
    Criar uma calculadora em Python com as seguintes funcionalidades:
    
    1. Operações básicas: soma, subtração, multiplicação e divisão
    2. Operações avançadas: potência, raiz quadrada, módulo
    3. Histórico das últimas 10 operações
    4. Interface via linha de comando (CLI)
    5. Tratamento de erros (divisão por zero, entrada inválida)
    6. Testes unitários com pytest
    7. Documentação com docstrings
    
    O código deve ser bem estruturado, seguir PEP8 e ser facilmente extensível.
    """

    # Inicializar componentes
    manager = AgentManager()
    await manager.initialize()

    analyst = manager.requirements_analyst

    # ==========================================
    # FASE 1: ANÁLISE DE REQUISITOS
    # ==========================================
    print("\n📋 FASE 1: Analisando Requisitos...")

    requirement = await analyst.analyze_requirements(project_description)
    print(f"✅ Requisito criado: {requirement.id}")
    print(f"   Título: {requirement.title}")
    print(f"   Prioridade: {requirement.priority}")
    print(f"   User Story: {requirement.user_story}")
    print(f"   Critérios de Aceitação: {len(requirement.acceptance_criteria)}")

    # ==========================================
    # FASE 2: GERAÇÃO DE DOCUMENTAÇÃO
    # ==========================================
    print("\n📄 FASE 2: Gerando Documentação...")

    docs = await analyst.generate_documentation(requirement.id, "technical")
    print(f"✅ Documentação gerada ({len(docs)} caracteres)")

    # ==========================================
    # FASE 3: GERAÇÃO DE CASOS DE TESTE
    # ==========================================
    print("\n🧪 FASE 3: Gerando Casos de Teste...")

    test_cases = await analyst.generate_test_cases(requirement.id, "python")
    print(f"✅ {len(test_cases)} casos de teste gerados")

    test_code = await analyst.generate_test_code(requirement.id, "python")
    print(f"✅ Código de testes gerado ({len(test_code)} caracteres)")

    # ==========================================
    # FASE 4: PREPARAR TAREFA PARA PROGRAMADOR
    # ==========================================
    print("\n👨‍💻 FASE 4: Preparando tarefa para Programador...")

    task_package = await analyst.prepare_task_for_programmer(requirement.id, "python")
    print("✅ Pacote de tarefa preparado")

    # ==========================================
    # FASE 5: EXECUTAR COM AGENTE PYTHON
    # ==========================================
    print("\n🐍 FASE 5: Executando com Agente Python...")

    python_agent = manager.get_or_create_agent("python")
    print(f"   Agente: {python_agent.name}")

    task = python_agent.create_task(
        task_package["task_description"],
        {"requirement_id": requirement.id, "project_name": "python-calculator"},
    )
    print(f"   Task criada: {task.id}")

    # Executar task
    result_task = await python_agent.execute_task(task.id)
    print(f"✅ Task executada - Status: {result_task.status.value}")
    print(f"   Iterações: {result_task.iterations}")

    # ==========================================
    # FASE 6: REVISÃO PELO ANALISTA
    # ==========================================
    print("\n🔍 FASE 6: Revisão pelo Analista...")

    validation = await analyst.validate_agent_output(
        requirement.id, result_task, python_agent
    )

    review = validation["review"]
    print("✅ Revisão concluída")
    print(f"   Status: {review['status']}")
    print(f"   Aprovado: {validation['approved']}")

    if review.get("issues_found"):
        print(f"   Issues encontrados: {len(review['issues_found'])}")
    if review.get("suggestions"):
        print(f"   Sugestões: {len(review['suggestions'])}")

    # ==========================================
    # FASE 7: CRIAR ARQUIVOS DO PROJETO
    # ==========================================
    print("\n📁 FASE 7: Criando arquivos do projeto...")

    from pathlib import Path

    project_dir = Path("/home/homelab/myClaude/dev_projects/python/python-calculator")
    project_dir.mkdir(parents=True, exist_ok=True)

    # Criar arquivos
    files = {
        "calculator.py": result_task.code,
        "test_calculator.py": result_task.tests if result_task.tests else test_code,
        "README.md": await analyst.generate_readme(requirement.id, "Python Calculator"),
        "requirements.txt": "pytest>=7.0.0\nblack\nmypy\n",
        ".gitignore": "__pycache__/\n*.pyc\n.pytest_cache/\n.mypy_cache/\nvenv/\n.env\n",
    }

    for filename, content in files.items():
        filepath = project_dir / filename
        filepath.write_text(content)
        print(f"   ✅ {filename}")

    # ==========================================
    # FASE 8: PUSH PARA GITHUB
    # ==========================================
    print("\n🐙 FASE 8: Push para GitHub...")

    github_result = await manager.push_to_github(
        language="python",
        project_name="python-calculator",
        repo_name="python-calculator",
        description="Calculadora Python criada pelo sistema de agentes com análise de requisitos",
    )

    if github_result.get("success"):
        repo_url = github_result.get("html_url", github_result.get("url", ""))
        print("✅ Repositório criado com sucesso!")
        print(f"\n{'=' * 60}")
        print("🔗 LINK DO REPOSITÓRIO GITHUB:")
        print(f"   {repo_url}")
        print(f"{'=' * 60}")
        return repo_url
    else:
        print(
            f"⚠️ Erro no push para GitHub: {github_result.get('error', 'Unknown error')}"
        )

        # Tentar criar via API direta
        print("\n📤 Tentando criar repositório via API direta...")

        github_client = GitHubAgentClient()

        # Preparar arquivos
        repo_files = {}
        for filename, content in files.items():
            repo_files[filename] = content

        create_result = await github_client.execute(
            "create_repo",
            {
                "name": "python-calculator",
                "description": "Calculadora Python criada pelo sistema de agentes com análise de requisitos",
                "private": False,
                "files": repo_files,
            },
        )

        if create_result.get("success"):
            repo_url = create_result.get("html_url", create_result.get("url", ""))
            print("✅ Repositório criado!")
            print(f"\n{'=' * 60}")
            print("🔗 LINK DO REPOSITÓRIO GITHUB:")
            print(f"   {repo_url}")
            print(f"{'=' * 60}")
            return repo_url
        else:
            print(
                f"❌ Erro: {create_result.get('error', 'Falha ao criar repositório')}"
            )
            print("\n📂 Projeto salvo localmente em:")
            print(f"   {project_dir}")
            return str(project_dir)

    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO DO PROJETO")
    print("=" * 60)
    print(f"Requisito: {requirement.id}")
    print(f"Status Task: {result_task.status.value}")
    print(f"Aprovação: {'✅ Aprovado' if validation['approved'] else '⚠️ Pendente'}")
    print(f"Arquivos: {len(files)}")
    print("=" * 60)


if __name__ == "__main__":
    result = asyncio.run(create_calculator_project())
    print(f"\nResultado final: {result}")
