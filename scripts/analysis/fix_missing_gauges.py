#!/usr/bin/env python3
"""
Fix Missing Gauges - Popula métricas faltantes no Prometheus
Método: Push Gateway ou HTTP Server local
"""
import time
from prometheus_client import start_http_server, Gauge, Counter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Definir métricas faltantes
agent_count_total = Gauge('agent_count_total', 'Total de agents ativos')
message_rate_total = Gauge('message_rate_total', 'Taxa de mensagens por segundo')

def update_metrics():
    """Atualiza métricas com valores mockados"""
    # Mock values - substitua com queries reais ao database
    agent_count_total.set(5)  # 5 agents ativos (exemplo)
    message_rate_total.set(12.5)  # 12.5 msgs/s (exemplo)
    logger.info("✅ Métricas atualizadas: agent_count=5, message_rate=12.5")

if __name__ == '__main__':
    # Iniciar servidor HTTP na porta 9102
    port = 9102
    start_http_server(port)
    logger.info(f"🚀 Servidor de métricas iniciado em http://localhost:{port}")
    logger.info(f"📊 Métricas disponíveis em http://localhost:{port}/metrics")
    logger.info("⚠️  NOTA: Configure Prometheus para scrape http://localhost:9102")
    
    try:
        while True:
            update_metrics()
            time.sleep(30)  # Atualizar a cada 30s
    except KeyboardInterrupt:
        logger.info("Parando servidor...")
