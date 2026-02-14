#!/usr/bin/env python3
"""
Fix para métricas do dashboard - adiciona agent_active_count e agent_message_rate_per_second
Roda como endpoint adicional no agent-network-exporter
"""
import os
from prometheus_client import Gauge, start_http_server
from sqlalchemy import create_engine, text
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Métricas sem labels para o dashboard
agent_count_metric = Gauge(
    'agent_active_count',
    'Total de agents ativos nas últimas 24h'
)

message_rate_metric = Gauge(
    'agent_message_rate_per_second',
    'Taxa global de mensagens por segundo (última hora)'
)

def update_dashboard_metrics():
    """Atualiza métricas para o dashboard"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set")
        return
    
    try:
        engine = create_engine(database_url, pool_size=2, max_overflow=3)
        
        with engine.connect() as conn:
            # Total de agents ativos (distintos nas últimas 24h)
            active_agents_count = conn.execute(text("""
                SELECT COUNT(DISTINCT source) 
                FROM messages 
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """)).scalar()
            
            agent_count_metric.set(active_agents_count or 0)
            logger.info(f"agent_active_count: {active_agents_count}")
            
            # Taxa de mensagens por segundo (última hora)
            msg_rate = conn.execute(text("""
                SELECT CAST(COUNT(*) AS FLOAT) / 3600.0
                FROM messages 
                WHERE timestamp > NOW() - INTERVAL '1 hour'
            """)).scalar()
            
            message_rate_metric.set(msg_rate or 0.0)
            logger.info(f"agent_message_rate_per_second: {msg_rate:.4f}")
            
    except Exception as e:
        logger.error(f"Erro ao atualizar métricas: {e}")

def main():
    """Entry point"""
    port = 9104  # Porta diferente (9102 é whatsapp-exporter)
    
    logger.info(f"Iniciando servidor de métricas do dashboard na porta {port}")
    start_http_server(port)
    
    while True:
        update_dashboard_metrics()
        time.sleep(60)  # Atualiza a cada 60s

if __name__ == '__main__':
    main()
