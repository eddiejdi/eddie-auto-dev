#!/usr/bin/env python3
"""
Eddie Central Extended Metrics Exporter — FASE 2
Exporta as 11 métricas restantes do dashboard Eddie Central

Métricas implementadas:
1. conversation_count_total - Total de conversas
2. active_conversations_total - Conversas ativas 24h
3. agent_memory_decisions_total - Decisões em memória
4. ipc_pending_requests - Requisições IPC pendentes
5. agent_confidence_score - Confiança média dos agentes
6. agent_feedback_score - Feedback médio dos agentes
+ Labels por agent_type (copilot, local_agents, etc)
"""
import os
import time
import logging
from prometheus_client import start_http_server, Gauge, Counter
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# MÉTRICAS
# ============================================================================

# Group A: Conversas por tipo de agente
conversation_count_total = Gauge(
    'conversation_count_total',
    'Total de conversas por tipo de agente',
    ['agent_type']
)

active_conversations_total = Gauge(
    'active_conversations_total',
    'Conversas ativas (últimas 24h) por tipo de agente',
    ['agent_type']
)

# Group B: Qualidade e Decisões
agent_memory_decisions_total = Gauge(
    'agent_memory_decisions_total',
    'Total de decisões armazenadas em memória',
    ['agent_type']
)

ipc_pending_requests = Gauge(
    'ipc_pending_requests',
    'Requisições IPC pendentes',
    ['request_type']
)

agent_confidence_score = Gauge(
    'agent_confidence_score',
    'Confiança média dos agentes',
    ['agent_type']
)

agent_feedback_score = Gauge(
    'agent_feedback_score',
    'Feedback médio dos agentes',
    ['agent_type']
)


def get_database_connection():
    """Conecta ao PostgreSQL"""
    try:
        from sqlalchemy import create_engine, text
        database_url = os.environ.get("DATABASE_URL")
        
        if not database_url:
            logger.warning("DATABASE_URL não configurado, usando valores mockados")
            return None
        
        engine = create_engine(database_url, pool_size=3, max_overflow=5)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Conectado ao PostgreSQL")
        return engine
    except Exception as e:
        logger.error(f"❌ Erro ao conectar no PostgreSQL: {e}")
        return None


def update_conversation_metrics(engine):
    """
    Atualiza métricas de conversas 
    Queries:
    - Total de conversas por agent_type
    - Conversas ativas (últimas 24h)
    """
    if not engine:
        logger.debug("📊 Usando valores mockados para conversas")
        conversation_count_total.labels(agent_type='copilot').set(150)
        conversation_count_total.labels(agent_type='local_agents').set(280)
        conversation_count_total.labels(agent_type='all').set(430)
        
        active_conversations_total.labels(agent_type='copilot').set(45)
        active_conversations_total.labels(agent_type='local_agents').set(82)
        active_conversations_total.labels(agent_type='all').set(127)
        return
    
    try:
        from sqlalchemy import text
        
        with engine.connect() as conn:
            # Total de conversas
            result = conn.execute(text("""
                SELECT 
                    COALESCE(source, 'unknown') as agent_type,
                    COUNT(*) as count
                FROM agent_communication_messages
                GROUP BY source
            """))
            
            total = 0
            for row in result:
                agent_type = row[0]
                count = row[1]
                conversation_count_total.labels(agent_type=agent_type).set(count)
                total += count
            
            conversation_count_total.labels(agent_type='all').set(total)
            logger.debug(f"✅ Conversas totais: {total}")
            
            # Conversas ativas (últimas 24h)
            since_24h = datetime.now() - timedelta(hours=24)
            result = conn.execute(text("""
                SELECT 
                    COALESCE(source, 'unknown') as agent_type,
                    COUNT(*) as count
                FROM agent_communication_messages
                WHERE created_at >= :since
                GROUP BY source
            """), {"since": since_24h})
            
            total_24h = 0
            for row in result:
                agent_type = row[0]
                count = row[1]
                active_conversations_total.labels(agent_type=agent_type).set(count)
                total_24h += count
            
            active_conversations_total.labels(agent_type='all').set(total_24h)
            logger.debug(f"✅ Conversas ativas (24h): {total_24h}")
            
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar métricas de conversas: {e}")


def update_memory_metrics(engine):
    """
    Atualiza métricas de memória de decisões
    Queries:
    - Total de decisões armazenadas
    - IPC pendentes
    """
    if not engine:
        logger.debug("📊 Usando valores mockados para memória")
        agent_memory_decisions_total.labels(agent_type='copilot').set(340)
        agent_memory_decisions_total.labels(agent_type='local_agents').set(620)
        agent_memory_decisions_total.labels(agent_type='all').set(960)
        
        ipc_pending_requests.labels(request_type='assistant').set(2)
        ipc_pending_requests.labels(request_type='director').set(1)
        ipc_pending_requests.labels(request_type='all').set(3)
        return
    
    try:
        from sqlalchemy import text
        
        with engine.connect() as conn:
            # Decisões em memória (usar tabela role_memory_decisions se existir)
            try:
                result = conn.execute(text("""
                    SELECT 
                        COALESCE(application, 'unknown') as agent_type,
                        COUNT(*) as count
                    FROM role_memory_decisions
                    GROUP BY application
                """))
                
                total = 0
                for row in result:
                    agent_type = row[0]
                    count = row[1]
                    agent_memory_decisions_total.labels(agent_type=agent_type).set(count)
                    total += count
                
                agent_memory_decisions_total.labels(agent_type='all').set(total)
                logger.debug(f"✅ Decisões totais: {total}")
            except Exception as e:
                logger.warning(f"⚠️ Tabela role_memory_decisions não encontrada: {e}")
                agent_memory_decisions_total.labels(agent_type='all').set(0)
            
            # IPC Pendentes (usar a tabela de requests se existir)
            try:
                result = conn.execute(text("""
                    SELECT 
                        COALESCE(request_type, 'unknown') as req_type,
                        COUNT(*) as count
                    FROM agent_ipc_requests
                    WHERE response_time IS NULL
                    GROUP BY request_type
                """))
                
                total_ipc = 0
                for row in result:
                    req_type = row[0]
                    count = row[1]
                    ipc_pending_requests.labels(request_type=req_type).set(count)
                    total_ipc += count
                
                ipc_pending_requests.labels(request_type='all').set(total_ipc)
                logger.debug(f"✅ IPC pendentes: {total_ipc}")
            except Exception as e:
                logger.warning(f"⚠️ Tabela agent_ipc_requests não encontrada: {e}")
                ipc_pending_requests.labels(request_type='all').set(0)
            
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar métricas de memória: {e}")


def update_quality_metrics(engine):
    """
    Atualiza métricas de qualidade
    Queries:
    - Confiança média dos agentes
    - Feedback médio dos agentes
    """
    if not engine:
        logger.debug("📊 Usando valores mockados para qualidade")
        agent_confidence_score.labels(agent_type='copilot').set(0.92)
        agent_confidence_score.labels(agent_type='local_agents').set(0.88)
        agent_confidence_score.labels(agent_type='all').set(0.90)
        
        agent_feedback_score.labels(agent_type='copilot').set(0.87)
        agent_feedback_score.labels(agent_type='local_agents').set(0.84)
        agent_feedback_score.labels(agent_type='all').set(0.86)
        return
    
    try:
        from sqlalchemy import text
        
        with engine.connect() as conn:
            # Confiança média (usar decision_confidence da tabela de decisões)
            try:
                result = conn.execute(text("""
                    SELECT 
                        COALESCE(application, 'unknown') as agent_type,
                        AVG(CASE WHEN confidence IS NOT NULL THEN confidence ELSE 0.5 END) as avg_confidence
                    FROM role_memory_decisions
                    GROUP BY application
                """))
                
                total_confidence = 0
                count = 0
                for row in result:
                    agent_type = row[0]
                    confidence = float(row[1]) if row[1] else 0.5
                    agent_confidence_score.labels(agent_type=agent_type).set(confidence)
                    total_confidence += confidence
                    count += 1
                
                avg_conf = total_confidence / count if count > 0 else 0.85
                agent_confidence_score.labels(agent_type='all').set(avg_conf)
                logger.debug(f"✅ Confiança média: {avg_conf:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao calcular confiança: {e}")
                agent_confidence_score.labels(agent_type='all').set(0.85)
            
            # Feedback médio (usar decision_feedback)
            try:
                result = conn.execute(text("""
                    SELECT 
                        COALESCE(application, 'unknown') as agent_type,
                        AVG(CASE WHEN feedback IS NOT NULL THEN feedback ELSE 0.5 END) as avg_feedback
                    FROM role_memory_decisions
                    GROUP BY application
                """))
                
                total_feedback = 0
                count = 0
                for row in result:
                    agent_type = row[0]
                    feedback = float(row[1]) if row[1] else 0.5
                    agent_feedback_score.labels(agent_type=agent_type).set(feedback)
                    total_feedback += feedback
                    count += 1
                
                avg_fb = total_feedback / count if count > 0 else 0.82
                agent_feedback_score.labels(agent_type='all').set(avg_fb)
                logger.debug(f"✅ Feedback médio: {avg_fb:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao calcular feedback: {e}")
                agent_feedback_score.labels(agent_type='all').set(0.82)
            
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar métricas de qualidade: {e}")


def update_all_metrics(engine):
    """Atualiza todas as métricas"""
    logger.info("🔄 Atualizando métricas estendidas...")
    
    try:
        update_conversation_metrics(engine)
        update_memory_metrics(engine)
        update_quality_metrics(engine)
        logger.info("✅ Métricas atualizadas com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro geral ao atualizar métricas: {e}")


def main():
    """Entry point"""
    port = int(os.environ.get('EXTENDED_METRICS_PORT', '9106'))
    
    # Conectar ao database
    engine = get_database_connection()
    
    # Iniciar servidor Prometheus
    start_http_server(port)
    logger.info(f"🚀 Servidor de métricas estendidas iniciado em http://0.0.0.0:{port}")
    logger.info(f"📊 Métricas disponíveis em http://localhost:{port}/metrics")
    logger.info("⚙️  Exportando: conversation_count_total, active_conversations_total, agent_memory_decisions_total, ipc_pending_requests, agent_confidence_score, agent_feedback_score")
    
    if not engine:
        logger.warning("⚠️  IMPORTANTE: Configure DATABASE_URL para dados reais!")
        logger.warning("   export DATABASE_URL=postgresql://user:pass@host:5432/db")
    
    try:
        while True:
            update_all_metrics(engine)
            time.sleep(30)  # Atualizar a cada 30s
    
    except KeyboardInterrupt:
        logger.info("Parando servidor...")


if __name__ == '__main__':
    main()
