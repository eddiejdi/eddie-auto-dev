#!/usr/bin/env python3
"""
Test Agent Memory System
Valida o sistema de memória persistente dos agentes
"""
import os
import sys
import asyncio
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from specialized_agents.agent_memory import get_agent_memory, AgentMemory


async def test_basic_memory():
    """Teste básico de armazenamento e recuperação"""
    print("=" * 60)
    print("TEST 1: Armazenamento e Recuperação Básica")
    print("=" * 60)
    
    memory = get_agent_memory("test_agent")
    
    # Registra uma decisão
    decision_id = memory.record_decision(
        application="my-api",
        component="auth-service",
        error_type="authentication_error",
        error_message="Token expired after 5 minutes",
        decision_type="fix",
        decision="Increase token expiration to 30 minutes",
        reasoning="Short expiration causing too many re-authentications",
        confidence=0.8,
        context_data={"error_count": 45, "time_window": "1h"}
    )
    
    print(f"✓ Decisão registrada: ID={decision_id}")
    
    # Busca decisões similares
    similar = memory.recall_similar_decisions(
        application="my-api",
        component="auth-service",
        error_type="authentication_error",
        error_message="Token expired after 5 minutes",
        limit=3
    )
    
    print(f"✓ Decisões similares encontradas: {len(similar)}")
    if similar:
        for s in similar:
            print(f"  - {s['decision_type']}: {s['decision']} (confidence: {s['confidence']})")
    
    return decision_id


async def test_decision_learning():
    """Teste de aprendizado com múltiplas decisões"""
    print("\n" + "=" * 60)
    print("TEST 2: Aprendizado com Decisões Repetidas")
    print("=" * 60)
    
    memory = get_agent_memory("test_agent")
    
    # Simula 3 tentativas de deploy com mesmo erro
    decisions = []
    
    # 1ª tentativa - deploy direto (falhou)
    dec1 = memory.record_decision(
        application="payment-service",
        component="processor",
        error_type="memory_leak",
        error_message="Memory usage grows to 2GB after 1000 requests",
        decision_type="deploy",
        decision="Deploy with current code",
        reasoning="Memory leak não identificado ainda",
        confidence=0.5
    )
    decisions.append(dec1)
    print(f"✓ Decisão 1 (deploy): ID={dec1}")
    
    # Atualiza resultado - FALHOU
    memory.update_decision_outcome(dec1, "failure", 
                                   {"error": "Service crashed in production"},
                                   feedback_score=-0.8)
    print(f"  → Resultado: FALHA (crash em produção)")
    
    await asyncio.sleep(0.1)
    
    # 2ª tentativa - deploy com patch rápido (falhou também)
    dec2 = memory.record_decision(
        application="payment-service",
        component="processor",
        error_type="memory_leak",
        error_message="Memory usage grows to 2GB after 1000 requests",
        decision_type="fix",
        decision="Add memory cleanup every 500 requests",
        reasoning="Tentativa de cleanup periódico",
        confidence=0.6
    )
    decisions.append(dec2)
    print(f"✓ Decisão 2 (fix rápido): ID={dec2}")
    
    memory.update_decision_outcome(dec2, "failure",
                                   {"error": "Still crashes after 2000 requests"},
                                   feedback_score=-0.6)
    print(f"  → Resultado: FALHA (ainda crasha)")
    
    await asyncio.sleep(0.1)
    
    # 3ª tentativa - análise profunda (sucesso!)
    dec3 = memory.record_decision(
        application="payment-service",
        component="processor",
        error_type="memory_leak",
        error_message="Memory usage grows to 2GB after 1000 requests",
        decision_type="investigate",
        decision="Deep investigation with profiler before deploy",
        reasoning="Duas tentativas falharam, necessária análise completa",
        confidence=0.9
    )
    decisions.append(dec3)
    print(f"✓ Decisão 3 (investigação): ID={dec3}")
    
    memory.update_decision_outcome(dec3, "success",
                                   {"finding": "Connection pool not releasing properly"},
                                   feedback_score=1.0)
    print(f"  → Resultado: SUCESSO (encontrou causa raiz)")
    
    # Agora testa recall - deve encontrar as 3
    print(f"\n→ Buscando decisões similares...")
    similar = memory.recall_similar_decisions(
        application="payment-service",
        component="processor",
        error_type="memory_leak",
        error_message="Memory usage grows to 2GB after 1000 requests",
        limit=10
    )
    
    print(f"✓ Total de decisões encontradas: {len(similar)}")
    print(f"\nHistórico de aprendizado:")
    for i, s in enumerate(similar, 1):
        outcome = s.get('outcome', 'pending')
        feedback = s.get('feedback_score', 0)
        print(f"  {i}. {s['decision_type']}: {s['decision'][:50]}...")
        print(f"     Resultado: {outcome} (feedback: {feedback:.1f})")
        print(f"     Confiança: {s['confidence']:.2f}")
        print()


async def test_pattern_learning():
    """Teste de aprendizado de padrões"""
    print("\n" + "=" * 60)
    print("TEST 3: Aprendizado de Padrões")
    print("=" * 60)
    
    memory = get_agent_memory("test_agent")
    
    # Registra padrões
    memory.learn_pattern(
        pattern_type="error_recovery",
        pattern_data={
            "error": "database_connection_timeout",
            "solution": "implement_retry_with_backoff",
            "max_retries": 3
        },
        success=True
    )
    print("✓ Padrão 1 aprendido: database retry")
    
    # Mesmo padrão novamente (sucesso)
    memory.learn_pattern(
        pattern_type="error_recovery",
        pattern_data={
            "error": "database_connection_timeout",
            "solution": "implement_retry_with_backoff",
            "max_retries": 3
        },
        success=True
    )
    print("✓ Padrão 1 reforçado (2ª ocorrência)")
    
    # Outro padrão com falha
    memory.learn_pattern(
        pattern_type="deployment_check",
        pattern_data={
            "check": "memory_usage",
            "threshold": "1GB",
            "action": "reject_deploy"
        },
        success=False
    )
    print("✓ Padrão 2 aprendido: memory check (falhou)")
    
    # Busca padrões aprendidos
    patterns = memory.get_learned_patterns(min_confidence=0.5, min_occurrences=1)
    print(f"\n✓ Total de padrões: {len(patterns)}")
    
    for p in patterns:
        print(f"\n  Padrão: {p['pattern_type']}")
        print(f"  Ocorrências: {p['occurrences']}")
        print(f"  Sucessos: {p['success_count']}, Falhas: {p['failure_count']}")
        print(f"  Confiança: {p['confidence']:.2f}")


async def test_statistics():
    """Teste de estatísticas"""
    print("\n" + "=" * 60)
    print("TEST 4: Estatísticas de Decisões")
    print("=" * 60)
    
    memory = get_agent_memory("test_agent")
    
    stats = memory.get_decision_statistics(days_back=7)
    
    print(f"✓ Estatísticas dos últimos 7 dias:")
    print(f"  Total de decisões: {stats.get('total_decisions', 0)}")
    print(f"  Aplicações únicas: {stats.get('applications_count', 0)}")
    print(f"  Componentes únicos: {stats.get('components_count', 0)}")
    print(f"  Erros únicos: {stats.get('unique_errors', 0)}")
    print(f"  Confiança média: {stats.get('avg_confidence', 0):.2f}")
    print(f"  Sucessos: {stats.get('successes', 0)}")
    print(f"  Falhas: {stats.get('failures', 0)}")
    
    print(f"\n  Decisões por tipo:")
    for dtype, count in stats.get('decisions_by_type', {}).items():
        print(f"    - {dtype}: {count}")


async def main():
    """Executa todos os testes"""
    print("\n" + "=" * 60)
    print("AGENT MEMORY SYSTEM - VALIDATION TESTS")
    print("=" * 60)
    
    # Verifica DATABASE_URL
    if not os.environ.get('DATABASE_URL'):
        print("\n⚠️  DATABASE_URL não configurado!")
        print("   Configure com: export DATABASE_URL=postgresql://user:pass@host:5432/db")
        return
    
    print(f"\n✓ DATABASE_URL configurado")
    print(f"  Agent: test_agent")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Executa testes
        await test_basic_memory()
        await test_decision_learning()
        await test_pattern_learning()
        await test_statistics()
        
        print("\n" + "=" * 60)
        print("✓ TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ ERRO NOS TESTES: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
