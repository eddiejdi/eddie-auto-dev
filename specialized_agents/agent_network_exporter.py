"""
Agent Network Metrics Exporter
Exporta métricas de comunicação entre agents para visualização em rede neural no Grafana
"""
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
from collections import defaultdict
from prometheus_client import start_http_server, Gauge, Counter, Info
import logging

try:
    from sqlalchemy import create_engine, text
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

from .agent_communication_bus import get_communication_bus, MessageType
from .config import DATA_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentNetworkExporter:
    """
    Exporta métricas de comunicação entre agents para Prometheus/Grafana
    Permite visualização de rede neural mostrando fluxo de mensagens
    """
    
    def __init__(self, port: int = 9101):
        self.port = port
        self.database_url = os.environ.get("DATABASE_URL")
        self.engine = None
        
        if SQLALCHEMY_AVAILABLE and self.database_url:
            try:
                self.engine = create_engine(self.database_url, pool_size=3, max_overflow=5)
                logger.info(f"Conectado ao database: {self.database_url}")
            except Exception as e:
                logger.error(f"Erro ao conectar database: {e}")
        
        # Métricas Prometheus
        self._init_metrics()
        
        # Subscribe ao bus para métricas em tempo real
        bus = get_communication_bus()
        bus.subscribe(self._on_message)
        
        logger.info(f"✅ Agent Network Exporter inicializado na porta {port}")
    
    def _init_metrics(self):
        """Inicializa métricas Prometheus"""
        
        # Contador de mensagens entre pares de agents
        self.messages_between = Counter(
            'agent_messages_total',
            'Total de mensagens entre agents',
            ['source', 'target', 'type']
        )
        
        # Gauge de agents ativos
        self.active_agents = Gauge(
            'agent_active_count',
            'Número de agents ativos',
            ['agent']
        )
        
        # Latência média de resposta entre agents
        self.response_latency = Gauge(
            'agent_response_latency_seconds',
            'Latência média de resposta entre agents',
            ['source', 'target']
        )
        
        # Taxa de mensagens por segundo
        self.message_rate = Gauge(
            'agent_message_rate_per_second',
            'Taxa de mensagens por segundo',
            ['source', 'target']
        )
        
        # Força da conexão (baseado em volume de mensagens)
        self.connection_strength = Gauge(
            'agent_connection_strength',
            'Força da conexão entre agents (0-1)',
            ['source', 'target']
        )
        
        # Status do agent (info metric)
        self.agent_info = Info(
            'agent_info',
            'Informações sobre o agent'
        )
        
        # Contadores de tipos de mensagem por agent
        self.message_type_count = Counter(
            'agent_message_type_total',
            'Total de mensagens por tipo',
            ['agent', 'message_type']
        )
        
        # Erros por agent
        self.agent_errors = Counter(
            'agent_errors_total',
            'Total de erros por agent',
            ['agent', 'error_type']
        )
        
        # Conversas ativas
        self.active_conversations = Gauge(
            'agent_active_conversations',
            'Número de conversas ativas'
        )
        
        # Total de agents ativos sem labels (para dashboard)
        self.agent_count_total = Gauge(
            'agent_count_total',
            'Total de agents ativos nas últimas 24h'  
        )
        
        # Taxa de mensagens global sem labels (para dashboard)
        self.message_rate_total = Gauge(
            'message_rate_total',
            'Taxa global de mensagens por segundo'
        )

    
    def _on_message(self, message):
        """Callback para mensagens do bus - atualiza métricas em tempo real"""
        try:
            # Atualiza contador de mensagens
            self.messages_between.labels(
                source=message.source,
                target=message.target,
                type=message.message_type.value
            ).inc()
            
            # Atualiza contadores por tipo
            self.message_type_count.labels(
                agent=message.source,
                message_type=message.message_type.value
            ).inc()
            
            # Marca agent como ativo
            self.active_agents.labels(agent=message.source).set(1)
            
            # Se for erro, conta
            if message.message_type == MessageType.ERROR:
                error_type = message.metadata.get('error_type', 'unknown')
                self.agent_errors.labels(
                    agent=message.source,
                    error_type=error_type
                ).inc()
                
        except Exception as e:
            logger.error(f"Erro ao processar mensagem para métricas: {e}")
    
    def update_network_metrics(self):
        """Atualiza métricas de rede baseadas no histórico do database"""
        if not self.engine:
            logger.warning("Database não disponível para métricas de rede")
            return
        
        try:
            with self.engine.connect() as conn:
                # Busca mensagens das últimas 24h (com LIMIT para evitar OOM)
                result = conn.execute(text("""
                    SELECT 
                        source,
                        target,
                        message_type,
                        COUNT(*) as msg_count,
                        AVG(latency_seconds) as avg_latency
                    FROM (
                        SELECT 
                            source,
                            target,
                            message_type,
                            timestamp,
                            EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (PARTITION BY source, target ORDER BY timestamp))) as latency_seconds
                        FROM messages
                        WHERE timestamp > NOW() - INTERVAL '24 hours'
                    ) sub
                    GROUP BY source, target, message_type
                    LIMIT 1000
                """))
                
                # Calcula força das conexões (normalizado)
                max_messages = 0
                connections = []
                
                for row in result:
                    source, target, msg_type, count, latency = row
                    connections.append((source, target, count, latency))
                    if count > max_messages:
                        max_messages = count
                
                # Atualiza métricas
                for source, target, count, latency in connections:
                    # Força da conexão (normalizada 0-1)
                    strength = count / max_messages if max_messages > 0 else 0
                    self.connection_strength.labels(
                        source=source,
                        target=target
                    ).set(strength)
                    
                    # Latência média
                    if latency is not None:
                        self.response_latency.labels(
                            source=source,
                            target=target
                        ).set(latency)
                
                # Conversas ativas
                active = conn.execute(text("""
                    SELECT COUNT(DISTINCT id) 
                    FROM conversations 
                    WHERE status = 'active'
                """)).scalar()
                
                self.active_conversations.set(active or 0)
                
                # Métricas dashboard (sem labels)
                active_agents = conn.execute(text("""
                    SELECT COUNT(DISTINCT source) 
                    FROM messages 
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                """)).scalar()
                self.agent_count_total.set(active_agents or 0)
                
                msg_rate = conn.execute(text("""
                    SELECT CAST(COUNT(*) AS FLOAT) / 3600.0
                    FROM messages 
                    WHERE timestamp > NOW() - INTERVAL '1 hour'
                """)).scalar()
                self.message_rate_total.set(msg_rate or 0.0)
                
        except Exception as e:
            logger.error(f"Erro ao atualizar métricas de rede: {e}")
    
    def get_network_topology(self) -> Dict:
        """Retorna topologia da rede de agents para visualização"""
        if not self.engine:
            return {"nodes": [], "edges": []}
        
        try:
            with self.engine.connect() as conn:
                # Busca todos os agents (nós) com LIMIT
                agents_result = conn.execute(text("""
                    SELECT DISTINCT source as agent
                    FROM messages
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                    LIMIT 100
                    UNION
                    SELECT DISTINCT target as agent
                    FROM messages
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                    LIMIT 100
                """))
                
                nodes = []
                for row in agents_result:
                    agent = row[0]
                    if agent != 'all':  # Ignora broadcasts
                        nodes.append({
                            "id": agent,
                            "label": agent,
                            "group": self._classify_agent(agent)
                        })
                
                # Busca conexões (arestas) com LIMIT
                edges_result = conn.execute(text("""
                    SELECT 
                        source,
                        target,
                        COUNT(*) as weight,
                        MAX(timestamp) as last_interaction
                    FROM messages
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                    AND target != 'all'
                    GROUP BY source, target
                    HAVING COUNT(*) > 0
                    LIMIT 500
                """))
                
                edges = []
                for row in edges_result:
                    source, target, weight, last_interaction = row
                    edges.append({
                        "from": source,
                        "to": target,
                        "weight": int(weight),
                        "last_interaction": last_interaction.isoformat() if last_interaction else None
                    })
                
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "generated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Erro ao gerar topologia: {e}")
            return {"nodes": [], "edges": [], "error": str(e)}
    
    def _classify_agent(self, agent_name: str) -> str:
        """Classifica agent em grupos para visualização"""
        agent_lower = agent_name.lower()
        
        if 'python' in agent_lower:
            return 'language'
        elif any(lang in agent_lower for lang in ['javascript', 'typescript', 'go', 'rust', 'java', 'csharp', 'php']):
            return 'language'
        elif 'coordinator' in agent_lower:
            return 'coordinator'
        elif 'diretor' in agent_lower:
            return 'director'
        elif 'telegram' in agent_lower:
            return 'interface'
        elif 'llm' in agent_lower:
            return 'llm'
        else:
            return 'other'
    
    def export_to_json(self, filepath: str = None):
        """Exporta topologia para JSON (para importação manual no Grafana)"""
        if filepath is None:
            filepath = f"{DATA_DIR}/agent_network_topology.json"
        
        topology = self.get_network_topology()
        
        with open(filepath, 'w') as f:
            json.dump(topology, f, indent=2)
        
        logger.info(f"Topologia exportada para: {filepath}")
        return filepath
    
    def run(self, update_interval: int = 60):
        """Inicia servidor de métricas e loop de atualização"""
        # Inicia servidor Prometheus
        start_http_server(self.port)
        logger.info(f"🚀 Servidor de métricas rodando em http://0.0.0.0:{self.port}")
        logger.info(f"⚙️  Intervalo de atualização: {update_interval}s (aumentado para evitar sobrecarga)")
        
        try:
            while True:
                # Atualiza métricas de rede
                self.update_network_metrics()
                
                # Exporta topologia
                self.export_to_json()
                
                # Aguarda próximo ciclo (60s padrão)
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            logger.info("Parando exporter...")


def main():
    """Entry point"""
    port = int(os.environ.get('AGENT_NETWORK_EXPORTER_PORT', 9101))
    exporter = AgentNetworkExporter(port=port)
    exporter.run()


if __name__ == '__main__':
    main()
