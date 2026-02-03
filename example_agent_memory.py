#!/usr/bin/env python3
"""
Exemplo Prático - Agent Memory System
Demonstra como usar o sistema de memória para tomar decisões informadas
"""
import os
import sys
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from specialized_agents.base_agent import SpecializedAgent, Task
from specialized_agents.language_agents import PythonAgent


async def example_deployment_decision():
    """Exemplo: Decisão de deploy com base em histórico"""
    print("=" * 70)
    print("EXEMPLO: Decisão de Deploy Informada por Memória")
    print("=" * 70)
    
    # Criar agente Python
    agent = PythonAgent()
    
    print(f"\n✓ Agente criado: {agent.name}")
    print(f"  Memória disponível: {agent.memory is not None}")
    
    if not agent.memory:
        print("\n⚠️  Memória não disponível. Configure DATABASE_URL.")
        return
    
    # Cenário: API com erro de memória
    application = "payment-api"
    component = "transaction-processor"
    error_type = "memory_leak"
    error_msg = "Memory grows from 500MB to 4GB after 10k requests"
    
    print(f"\n📦 Aplicação: {application}")
    print(f"   Componente: {component}")
    print(f"   Erro: {error_type}")
    print(f"   Mensagem: {error_msg}")
    
    # Consultar memória antes de decidir
    print(f"\n🔍 Consultando experiências passadas...")
    past_decisions = agent.recall_past_decisions(
        application, component, error_type, error_msg
    )
    
    if past_decisions:
        print(f"\n✓ Encontradas {len(past_decisions)} decisões anteriores:")
        for i, pd in enumerate(past_decisions[:3], 1):
            print(f"\n  {i}. {pd['decision_type'].upper()} (confiança: {pd['confidence']:.2f})")
            print(f"     Decisão: {pd['decision']}")
            print(f"     Resultado: {pd.get('outcome', 'pendente')}")
            if pd.get('feedback_score'):
                print(f"     Feedback: {pd['feedback_score']:.2f}")
    else:
        print(f"  Nenhuma decisão anterior encontrada.")
    
    # Tomar decisão informada usando LLM + memória
    print(f"\n🤖 Tomando decisão informada...")
    decision = await agent.make_informed_decision(
        application=application,
        component=component,
        error_type=error_type,
        error_message=error_msg,
        context={
            "current_memory_usage": "4GB",
            "request_count": 10000,
            "uptime": "2 hours"
        }
    )
    
    print(f"\n📋 DECISÃO TOMADA:")
    print(f"   Tipo: {decision['decision_type'].upper()}")
    print(f"   Decisão: {decision['decision']}")
    print(f"   Raciocínio: {decision['reasoning'][:200]}...")
    print(f"   Confiança: {decision['confidence']:.2f}")
    print(f"   Aprendeu do passado: {decision.get('learned_from_past', False)}")
    print(f"   Experiências consultadas: {decision.get('past_experiences', 0)}")
    
    if decision.get('memory_id'):
        print(f"   Registrado em memória: ID {decision['memory_id']}")
    
    # Simular resultado e atualizar feedback
    print(f"\n⏳ Simulando aplicação da decisão...")
    await asyncio.sleep(1)
    
    # Para este exemplo, vamos simular sucesso
    success = decision['decision_type'] != 'deploy'  # deploy direto = falha
    
    if decision.get('memory_id'):
        agent.update_decision_feedback(
            decision_id=decision['memory_id'],
            success=success,
            details={
                "deployed": decision['decision_type'] == 'deploy',
                "memory_after": "500MB" if success else "still 4GB",
                "notes": "Problem fixed with connection pool" if success else "Still crashes"
            }
        )
        result_text = "✓ SUCESSO" if success else "✗ FALHA"
        print(f"\n{result_text} - Feedback atualizado na memória")
    
    # Mostrar estatísticas
    stats = agent.memory.get_decision_statistics(
        application=application,
        days_back=30
    )
    
    print(f"\n📊 ESTATÍSTICAS PARA {application}:")
    print(f"   Total de decisões: {stats['total_decisions']}")
    print(f"   Taxa de sucesso: {stats['successes']}/{stats['successes'] + stats['failures']}")
    print(f"   Confiança média: {stats.get('avg_confidence', 0):.2f}")


async def example_repeated_error():
    """Exemplo: Como agente aprende com erros repetidos"""
    print("\n\n" + "=" * 70)
    print("EXEMPLO: Aprendizado com Erros Repetidos")
    print("=" * 70)
    
    agent = PythonAgent()
    
    if not agent.memory:
        print("\n⚠️  Memória não disponível.")
        return
    
    app = "user-service"
    comp = "authentication"
    error = "rate_limit_exceeded"
    msg = "API rate limit 1000 req/hour exceeded"
    
    print(f"\n📦 Aplicação: {app}")
    print(f"   Erro: {error}")
    
    # 1ª tentativa - aumentar limite
    print(f"\n--- Tentativa 1 ---")
    dec1_id = agent.should_remember_decision(
        application=app,
        component=comp,
        error_type=error,
        error_message=msg,
        decision_type="config_change",
        decision="Increase rate limit to 5000 req/hour",
        reasoning="Direct fix for rate limit",
        confidence=0.6
    )
    agent.update_decision_feedback(dec1_id, False, {"issue": "Still hitting limit"})
    print(f"  Decisão: Aumentar limite → FALHOU")
    
    # 2ª tentativa - caching
    print(f"\n--- Tentativa 2 ---")
    dec2_id = agent.should_remember_decision(
        application=app,
        component=comp,
        error_type=error,
        error_message=msg,
        decision_type="implement_cache",
        decision="Add Redis cache to reduce API calls",
        reasoning="Primeira tentativa falhou, tentar reduzir chamadas",
        confidence=0.8
    )
    agent.update_decision_feedback(dec2_id, True, {"reduction": "90% less API calls"})
    print(f"  Decisão: Implementar cache → SUCESSO!")
    
    # 3ª ocorrência do mesmo erro - consultar memória
    print(f"\n--- Nova Ocorrência do Mesmo Erro ---")
    similar = agent.recall_past_decisions(app, comp, error, msg)
    
    print(f"\n🧠 Memória consultada - {len(similar)} experiências:")
    for s in similar:
        outcome_emoji = "✓" if s['outcome'] == 'success' else "✗"
        print(f"  {outcome_emoji} {s['decision_type']}: {s['decision'][:50]}...")
    
    print(f"\n💡 Agente agora sabe que 'implementar cache' funciona!")
    print(f"   E que apenas 'aumentar limite' não resolve o problema.")


async def main():
    """Executa exemplos"""
    if not os.environ.get('DATABASE_URL'):
        print("\n⚠️  DATABASE_URL não configurado!")
        print("   Configure com: export DATABASE_URL=postgresql://user:pass@host:5432/db")
        print("\nExemplo:")
        print('   export DATABASE_URL="postgresql://postgres:postgres@192.168.15.2:5432/postgres"')
        return
    
    await example_deployment_decision()
    await example_repeated_error()
    
    print("\n\n" + "=" * 70)
    print("✓ EXEMPLOS CONCLUÍDOS")
    print("=" * 70)
    print("\nO sistema de memória permite que agentes:")
    print("  • Lembrem de decisões passadas")
    print("  • Aprendam com sucessos e falhas")
    print("  • Evitem repetir erros")
    print("  • Tomem decisões mais confiantes baseadas em experiência")


if __name__ == "__main__":
    asyncio.run(main())
