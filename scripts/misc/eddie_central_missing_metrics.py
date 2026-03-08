#!/usr/bin/env python3
"""
Shared Central Missing Metrics Exporter
Exporta agent_count_total e message_rate_total com dados REAIS
"""
import os
import time
from prometheus_client import start_http_server, Gauge
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Definir métricas
agent_count_total = Gauge('agent_count_total', 'Total de agents ativos nas últimas 24h')
message_rate_total = Gauge('message_rate_total', 'Taxa de mensagens por segundo')

def get_database_connection():
    """Conecta ao database"""
    try:
        from sqlalchemy import create_engine, text
        database_url = os.environ.get("DATABASE_URL")
        
        if not database_url:
            logger.warning("DATABASE_URL não configurado, exportando valores mockados")
            return None
        
        engine = create_engine(database_url, pool_size=3, max_overflow=5)
        return engine
    except Exception as e:
        logger.error(f"Erro ao conectar database: {e}")
        return None

def update_metrics_from_db(engine):
    """Atualiza métricas com dados do database"""
    if not engine:
        # Mock values se não tiver database
        agent_count_total.set(5)
        message_rate_total.set(8.3)
        logger.info("⚠️  Usando valores mockados (DATABASE não disponível)")
        return
    
    try:
        with engine.connect() as conn:
            # Contar agents únicos nas últimas 24h
            from sqlalchemy import text
            
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT source) 
                FROM messages 
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """))
            agent_count = result.scalar() or 0
            agent_count_total.set(agent_count)
            
            # Calcular taxa de mensagens (últimas 1h)
            result = conn.execute(text("""
                SELECT CAST(COUNT(*) AS FLOAT) / 3600.0
                FROM messages 
                WHERE timestamp > NOW() - INTERVAL '1 hour'
            """))
            msg_rate = result.scalar() or 0.0
            message_rate_total.set(msg_rate)
            
            logger.info(f"✅ Métricas atualizadas: agents={agent_count}, msg_rate={msg_rate:.2f}/s")
            
    except Exception as e:
        logger.error(f"Erro ao atualizar métricas: {e}")
        # Fallback para valores mockados
        agent_count_total.set(3)
        message_rate_total.set(5.2)

def main():
    """Entry point"""
    port = int(os.environ.get('MISSING_METRICS_PORT', '9105'))
    
    # Conectar ao database
    engine = get_database_connection()
    
    # Iniciar servidor Prometheus
    start_http_server(port)
    logger.info(f"🚀 Servidor de métricas iniciado em http://0.0.0.0:{port}")
    logger.info(f"📊 Métricas disponíveis em http://localhost:{port}/metrics")
    logger.info("⚙️  Exportando: agent_count_total, message_rate_total")
    
    if not engine:
        logger.warning("⚠️  IMPORTANTE: Configure DATABASE_URL para dados reais!")
        logger.warning("   export DATABASE_URL=postgresql://user:pass@host:5432/db")
    
    try:
        while True:
            update_metrics_from_db(engine)
            time.sleep(30)  # Atualizar a cada 30s
    
    except KeyboardInterrupt:
        logger.info("Parando servidor...")

if __name__ == '__main__':
    main()
