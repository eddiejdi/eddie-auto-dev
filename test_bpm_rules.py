#!/usr/bin/env python3
"""Teste de validação das regras herdadas do BPM Agent"""

from specialized_agents.bpm_agent import BPMAgent, AGENT_RULES, get_bpm_agent

def test_bpm_rules():
    print("✅ BPM Agent Validação")
    print("=" * 50)
    
    agent = get_bpm_agent()
    
    # 1. Verificar regras
    print("📋 AGENT_RULES:")
    for rule in AGENT_RULES.keys():
        print(f"   • {rule}")
    
    # 2. Verificar capabilities
    caps = agent.get_capabilities()
    print(f"\n📊 Capabilities:")
    print(f"   Versão: {caps['version']}")
    print(f"   Regras herdadas: {caps['rules_inherited']}")
    print(f"   Validação ativa: {caps['validation_enabled']}")
    
    # 3. Verificar métodos de validação
    print(f"\n🔍 Métodos disponíveis:")
    print(f"   validate_diagram: {hasattr(agent, 'validate_diagram')}")
    print(f"   get_rules: {hasattr(agent, 'get_rules')}")
    
    # 4. Testar get_rules
    rules = agent.get_rules()
    print(f"\n📜 get_rules() retorna: {len(rules)} regras")
    
    # 5. Testar validação de diagrama existente
    import os
    from pathlib import Path
    diagrams_dir = Path(__file__).parent / "specialized_agents" / "diagrams"
    if diagrams_dir.exists():
        for diagram in diagrams_dir.glob("*.drawio"):
            print(f"\n🔍 Validando: {diagram.name}")
            result = agent.validate_diagram(str(diagram))
            print(f"   Válido: {result['valid']}")
            print(f"   Checks: {result['checks_passed']}")
            if result['errors']:
                print(f"   Erros: {result['errors']}")
            if result['warnings']:
                print(f"   Warnings: {result['warnings']}")
            break
    
    print("\n✅ Validação completa!")
    return True

if __name__ == "__main__":
    test_bpm_rules()
