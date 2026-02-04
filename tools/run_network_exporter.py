#!/usr/bin/env python3
"""
Script para executar o Network Exporter como serviço
Exporta métricas Prometheus para visualização em rede neural no Grafana
"""
import sys
import logging
import signal
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from specialized_agents.agent_network_exporter import AgentNetworkExporter
from prometheus_client import start_http_server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def signal_handler(sig, frame):
    """Graceful shutdown"""
    logger.info("Shutting down Agent Network Exporter...")
    sys.exit(0)


def main():
    """Main entry point"""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Portas
    metrics_port = 9101  # Prometheus metrics
    
    # Iniciar servidor HTTP para métricas
    logger.info(f"Starting Prometheus metrics server on port {metrics_port}...")
    start_http_server(metrics_port)
    
    # Criar e iniciar exporter
    logger.info("Initializing Agent Network Exporter...")
    exporter = AgentNetworkExporter(port=metrics_port)
    
    # Atualizar métricas a cada 60 segundos
    logger.info("Starting metric update loop (60s interval)...")
    try:
        import time
        while True:
            try:
                exporter.update_network_metrics()
                time.sleep(60)
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
