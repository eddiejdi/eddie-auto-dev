#!/usr/bin/env python3
"""
Bus Exporter - Exporta métricas do AgentCommunicationBus para Prometheus
"""
import os
import sys
import time
import requests
import json
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bus-exporter')

# Config
BUS_API_URL = os.getenv('BUS_API_URL', 'http://localhost:8503')
EXPORTER_PORT = int(os.getenv('EXPORTER_PORT', 9100))
SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', 5))

# Métricas Prometheus
messages_total = Counter(
    'eddie_bus_messages_total',
    'Total de mensagens publicadas no bus',
    ['type', 'source', 'target']
)

messages_gauge = Gauge(
    'eddie_bus_messages_count',
    'Número de mensagens armazenadas no buffer',
)

message_by_type = Gauge(
    'eddie_bus_messages_by_type',
    'Mensagens por tipo',
    ['type']
)

message_by_source = Gauge(
    'eddie_bus_messages_by_source',
    'Mensagens por origem',
    ['source']
)

response_time = Histogram(
    'eddie_bus_api_response_time_seconds',
    'Tempo de resposta da API do bus'
)

api_health = Gauge(
    'eddie_bus_api_health',
    'Status de saúde da API (1=healthy, 0=error)'
)

last_message_timestamp = Gauge(
    'eddie_bus_last_message_timestamp',
    'Timestamp da última mensagem processada'
)


def fetch_bus_metrics():
    """Busca métricas do bus via API"""
    try:
        start = time.time()
        response = requests.get(
            f'{BUS_API_URL}/communication/messages',
            timeout=5
        )
        elapsed = time.time() - start
        response_time.observe(elapsed)
        
        if response.status_code == 200:
            api_health.set(1)
            data = response.json()
            
            # Total de mensagens
            messages_gauge.set(data.get('total', 0))
            
            # Por tipo
            by_type = data.get('stats', {}).get('by_type', {})
            for msg_type, count in by_type.items():
                message_by_type.labels(type=msg_type).set(count)
                messages_total.labels(
                    type=msg_type,
                    source='unknown',
                    target='unknown'
                ).inc(count)
            
            # Por origem
            by_source = data.get('stats', {}).get('by_source', {})
            for source, count in by_source.items():
                message_by_source.labels(source=source).set(count)
            
            # Última mensagem
            messages = data.get('messages', [])
            if messages:
                last_msg = messages[-1]
                timestamp = datetime.fromisoformat(
                    last_msg['timestamp'].replace('Z', '+00:00')
                ).timestamp()
                last_message_timestamp.set(timestamp)
                
                logger.info(
                    f"✓ Metrics updated: {data.get('total', 0)} messages "
                    f"({len(by_type)} types, {len(by_source)} sources)"
                )
        else:
            api_health.set(0)
            logger.error(f"API returned {response.status_code}")
            
    except Exception as e:
        api_health.set(0)
        logger.error(f"Error fetching metrics: {e}")


def run_exporter():
    """Loop principal do exporter"""
    logger.info(f"Starting bus exporter on port {EXPORTER_PORT}")
    logger.info(f"Polling bus API at {BUS_API_URL} every {SCRAPE_INTERVAL}s")
    
    start_http_server(EXPORTER_PORT)
    
    while True:
        try:
            fetch_bus_metrics()
        except Exception as e:
            logger.error(f"Exporter error: {e}")
        
        time.sleep(SCRAPE_INTERVAL)


if __name__ == '__main__':
    run_exporter()
