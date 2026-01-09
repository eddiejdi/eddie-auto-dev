#!/usr/bin/env python3
"""
Teste direto de criação de calculadora usando os agentes especializados
"""
import asyncio
import sys
import os

# Adicionar path corretamente
sys.path.insert(0, '/home/eddie/myClaude')
os.chdir('/home/eddie/myClaude')

from specialized_agents import get_agent_manager, AgentManager
from specialized_agents.base_agent import TaskStatus

async def main():
    print("="*60)
    print("  TESTE: CRIAÇÃO DE CALCULADORA COM LLM OTIMIZADO")
    print("="*60)
    print()
    
    # Inicializar manager
    print("[1/5] Inicializando Agent Manager...")
    manager = get_agent_manager()
    await manager.initialize()
    
    # Criar projeto
    print("[2/5] Enviando requisição para o agente Python...")
    print("      Aguarde enquanto o LLM gera o código...")
    print()
    
    description = """Calculadora CLI com:
- Soma, subtração, multiplicação, divisão
- Potenciação e raiz quadrada
- Memória para armazenar valores
- Histórico de operações"""
    
    result = await manager.create_project(
        language="python",
        description=description,
        project_name="calculadora_final"
    )
    
    print("[3/5] Processamento concluído!")
    print()
    
    # Mostrar resultado
    print("[4/5] RESULTADO:")
    print("-"*60)
    print(f"  Success: {result['success']}")
    print(f"  Agent: {result['agent']}")
    print(f"  Status: {result['task']['status']}")
    print(f"  Code Length: {len(result['task']['code'])} chars")
    print(f"  Tests Length: {len(result['task']['tests'])} chars")
    print(f"  Project Path: {result['task']['project_path']}")
    print()
    
    # Mostrar código gerado
    print("[5/5] CÓDIGO GERADO:")
    print("-"*60)
    code = result['task']['code']
    if code:
        print(code[:2000] + "..." if len(code) > 2000 else code)
    else:
        print("(código vazio)")
    print("-"*60)
    
    # Salvar em arquivo
    if code:
        with open("/tmp/calculadora_gerada.py", "w") as f:
            f.write(code)
        print(f"\n[OK] Código salvo em /tmp/calculadora_gerada.py")
    
    print("\n" + "="*60)
    print("  FIM DO TESTE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
