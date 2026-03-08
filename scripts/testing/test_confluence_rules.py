#!/usr/bin/env python3
"""Teste de validação das regras herdadas do Confluence Agent"""

from specialized_agents.confluence_agent import ConfluenceAgent, AGENT_RULES, get_confluence_agent

def test_confluence_rules():
    print("✅ Confluence Agent Validação")
    print("=" * 50)
    
    agent = get_confluence_agent()
    
    # 1. Verificar regras herdadas
    print("📋 AGENT_RULES (herdadas conforme Regra 7):")
    for rule in AGENT_RULES.keys():
        print(f"   • {rule}")
    
    # 2. Verificar capabilities
    caps = agent.get_capabilities()
    print(f"\n📊 Capabilities:")
    print(f"   Nome: {caps['name']}")
    print(f"   Versão: {caps['version']}")
    print(f"   Templates: {len(caps['templates'])}")
    print(f"   Macros suportadas: {len(caps['macros_supported'])}")
    print(f"   Regras herdadas: {caps['rules_inherited']}")
    print(f"   Validação ativa: {caps['validation_enabled']}")
    
    # 3. Verificar templates
    print(f"\n📝 Templates disponíveis ({len(agent.list_templates())}):")
    for t in agent.list_templates():
        print(f"   • {t}")
    
    # 4. Gerar e validar documentos de exemplo
    print("\n🔍 Gerando documentos de exemplo:")
    
    templates_to_test = ["adr", "rfc", "api_doc"]
    for template in templates_to_test:
        try:
            output = agent.create_from_template(template, title=f"Teste_{template.upper()}")
            validation = agent.validate_page(output)
            status = "✅" if validation["valid"] else "❌"
            print(f"   {status} {template}: {validation['checks_passed']}")
        except Exception as e:
            print(f"   ❌ {template}: {e}")
    
    # 5. Verificar métodos obrigatórios
    print(f"\n🔍 Métodos obrigatórios (Regra 0.2):")
    print(f"   validate_page: {hasattr(agent, 'validate_page')}")
    print(f"   get_rules: {hasattr(agent, 'get_rules')}")
    print(f"   get_capabilities: {hasattr(agent, 'get_capabilities')}")
    
    print("\n✅ Validação completa!")
    return True

if __name__ == "__main__":
    test_confluence_rules()
