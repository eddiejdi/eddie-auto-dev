#!/usr/bin/env python3
"""
Bus Conversation Monitor - Monitora conversas em tempo real do bus
Expõe um endpoint HTTP para consumo por Grafana
"""
import os
import json
import requests
import threading
from datetime import datetime, timedelta
from collections import deque, defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('conversation-monitor')

BUS_API_URL = os.getenv('BUS_API_URL', 'http://localhost:8503')
MONITOR_PORT = int(os.getenv('MONITOR_PORT', 8888))
HISTORY_MINUTES = int(os.getenv('HISTORY_MINUTES', 60))

# Buffer de conversas
conversations_buffer = deque(maxlen=500)
conversation_stats = {
    'total_messages': 0,
    'by_type': defaultdict(int),
    'by_source': defaultdict(int),
    'by_pair': defaultdict(int),  # source->target pairs
    'active_agents': set(),
    'last_update': None
}

lock = threading.Lock()


class ConversationHandler(BaseHTTPRequestHandler):
    """Handler HTTP para servir dados de conversas"""
    
    def do_GET(self):
        """Responde a requisições GET"""
        if self.path == '/conversations':
            self.send_conversations()
        elif self.path == '/stats':
            self.send_stats()
        elif self.path == '/health':
            self.send_health()
        else:
            self.send_404()
    
    def send_conversations(self):
        """Retorna conversas em formato JSON"""
        with lock:
            data = {
                'timestamp': datetime.now().isoformat(),
                'total': len(conversations_buffer),
                'conversations': [
                    {
                        'id': msg['id'],
                        'timestamp': msg['timestamp'],
                        'type': msg['type'],
                        'source': msg['source'],
                        'target': msg['target'],
                        'content': msg['content'][:500],  # Limita conteúdo
                        'content_truncated': len(msg['content']) > 500
                    }
                    for msg in list(conversations_buffer)
                ]
            }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def send_stats(self):
        """Retorna estatísticas das conversas"""
        with lock:
            data = {
                'timestamp': datetime.now().isoformat(),
                'total_messages': conversation_stats['total_messages'],
                'by_type': dict(conversation_stats['by_type']),
                'by_source': dict(conversation_stats['by_source']),
                'by_pair': dict(conversation_stats['by_pair']),
                'active_agents': list(conversation_stats['active_agents']),
                'agent_count': len(conversation_stats['active_agents']),
                'last_update': conversation_stats['last_update']
            }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def send_health(self):
        """Health check"""
        data = {'status': 'healthy', 'timestamp': datetime.now().isoformat()}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_404(self):
        """Retorna 404"""
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
    def log_message(self, format, *args):
        """Suprime logs HTTP padrão"""
        pass


def fetch_and_update_conversations():
    """Busca conversas do bus e atualiza buffer"""
    global conversations_buffer, conversation_stats
    
    while True:
        try:
            response = requests.get(
                f'{BUS_API_URL}/communication/messages',
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [])
                stats = data.get('stats', {})
                
                with lock:
                    # Limpar buffer e repopular (mantém ordenado)
                    conversations_buffer.clear()
                    for msg in messages:
                        conversations_buffer.append({
                            'id': msg['id'],
                            'timestamp': msg['timestamp'],
                            'type': msg['type'],
                            'source': msg['source'],
                            'target': msg['target'],
                            'content': msg['content']
                        })
                    
                    # Atualizar estatísticas
                    conversation_stats['total_messages'] = data.get('total', 0)
                    conversation_stats['by_type'] = stats.get('by_type', {})
                    conversation_stats['by_source'] = stats.get('by_source', {})
                    conversation_stats['last_update'] = datetime.now().isoformat()
                    
                    # Extrair pares source->target
                    by_pair = defaultdict(int)
                    for msg in messages:
                        pair = f"{msg['source']} → {msg['target']}"
                        by_pair[pair] += 1
                    conversation_stats['by_pair'] = by_pair
                    
                    # Agentes ativos
                    sources = set(msg['source'] for msg in messages)
                    targets = set(msg['target'] for msg in messages if msg['target'] != 'all')
                    conversation_stats['active_agents'] = sources | targets
                    
                    logger.info(
                        f"✓ {len(messages)} messages, "
                        f"{len(conversation_stats['active_agents'])} agents, "
                        f"{len(conversation_stats['by_type'])} types"
                    )
            
        except Exception as e:
            logger.error(f"Error fetching conversations: {e}")
        
        # Atualizar a cada 3 segundos
        threading.Event().wait(3)


def run_server():
    """Inicia servidor HTTP"""
    logger.info(f"Starting conversation monitor on port {MONITOR_PORT}")
    
    server = HTTPServer(('0.0.0.0', MONITOR_PORT), ConversationHandler)
    
    # Thread de atualização de conversas
    update_thread = threading.Thread(
        target=fetch_and_update_conversations,
        daemon=True
    )
    update_thread.start()
    
    logger.info("✓ Monitor started")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    run_server()
