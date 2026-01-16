#!/usr/bin/env python3
"""
Test Suite para Agent Conversation Interceptor
Valida todas as funcionalidades do sistema de interceptação
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Adicionar path
sys.path.insert(0, str(Path(__file__).parent))

from specialized_agents.agent_interceptor import (
    get_agent_interceptor, ConversationPhase, AgentConversationInterceptor
)
from specialized_agents.agent_communication_bus import (
    get_communication_bus, MessageType, AgentCommunicationBus
)


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_test(name: str, status: bool, message: str = ""):
    """Imprime resultado de teste"""
    icon = f"{Colors.GREEN}✅{Colors.RESET}" if status else f"{Colors.RED}❌{Colors.RESET}"
    print(f"{icon} {name}")
    if message:
        print(f"   {Colors.BLUE}→{Colors.RESET} {message}")


def print_header(title: str):
    """Imprime cabeçalho de seção"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def test_communication_bus():
    """Testa Agent Communication Bus"""
    print_header("Testing Agent Communication Bus")
    
    bus = get_communication_bus()
    
    # Teste 1: Publicar mensagem
    msg = bus.publish(
        message_type=MessageType.REQUEST,
        source="TestAgent1",
        target="TestAgent2",
        content="Test message",
        metadata={"test": True}
    )
    print_test("Publicar mensagem", msg is not None, f"Message ID: {msg.id if msg else 'None'}")
    
    # Teste 2: Verificar buffer
    messages = bus.get_messages(limit=1)
    print_test("Buffer recebeu mensagem", len(messages) > 0, f"Buffer size: {len(bus.message_buffer)}")
    
    # Teste 3: Filtros
    bus.set_filter("request", False)
    msg2 = bus.publish(
        message_type=MessageType.REQUEST,
        source="TestAgent1",
        target="TestAgent2",
        content="Filtered message",
        metadata={}
    )
    print_test("Filtro funcionando", msg2 is None, "Mensagem filtrada (esperado)")
    bus.set_filter("request", True)
    
    # Teste 4: Estatísticas
    stats = bus.get_stats()
    print_test("Estatísticas disponíveis", stats is not None, 
               f"Total: {stats['total_messages']} mensagens")
    
    # Teste 5: Pausa/Retoma
    bus.pause_recording()
    print_test("Pausa de gravação", not bus.recording, "Gravação pausada")
    
    bus.resume_recording()
    print_test("Retoma de gravação", bus.recording, "Gravação ativa")
    
    # Teste 6: Subscribers
    events_received = []
    def subscriber(msg):
        events_received.append(msg)
    
    bus.subscribe(subscriber)
    bus.publish(
        message_type=MessageType.RESPONSE,
        source="TestAgent3",
        target="TestAgent1",
        content="Subscriber test",
        metadata={}
    )
    print_test("Subscribers funcionando", len(events_received) > 0, 
               f"Eventos recebidos: {len(events_received)}")


def test_interceptor():
    """Testa Agent Conversation Interceptor"""
    print_header("Testing Agent Conversation Interceptor")
    
    interceptor = get_agent_interceptor()
    bus = get_communication_bus()
    
    # Limpar dados anteriores
    bus.clear()
    interceptor.active_conversations.clear()
    
    # Teste 1: Capturar conversa
    conv_id = "test_conv_001"
    
    bus.publish(
        message_type=MessageType.REQUEST,
        source="PythonAgent",
        target="TestAgent",
        content="Criar testes",
        metadata={"conversation_id": conv_id}
    )
    
    time_sleep = 0.1
    import time
    time.sleep(time_sleep)
    
    print_test("Conversa capturada", conv_id in interceptor.active_conversations,
               f"Conversas ativas: {len(interceptor.active_conversations)}")
    
    # Teste 2: Adicionar mensagens à conversa
    for i in range(5):
        bus.publish(
            message_type=MessageType.CODE_GEN,
            source="PythonAgent",
            target="TestAgent",
            content=f"Teste {i}",
            metadata={"conversation_id": conv_id}
        )
    
    conv = interceptor.get_conversation(conv_id)
    print_test("Mensagens coletadas", conv is not None and conv["message_count"] >= 5,
               f"Mensagens: {conv['message_count'] if conv else 0}")
    
    # Teste 3: Análise de conversa
    analysis = interceptor.analyze_conversation(conv_id)
    print_test("Análise funcionando", analysis is not None,
               f"Tipos: {len(analysis['message_types']) if analysis else 0}")
    
    # Teste 4: Snapshot
    snapshot = interceptor.take_snapshot(conv_id)
    print_test("Snapshot criado", snapshot is not None,
               f"Fase: {snapshot.phase.value if snapshot else 'N/A'}")
    
    # Teste 5: Export
    exported_json = interceptor.export_conversation(conv_id, format="json")
    print_test("Export JSON", exported_json is not None,
               f"Tamanho: {len(exported_json) if exported_json else 0} caracteres")
    
    exported_md = interceptor.export_conversation(conv_id, format="markdown")
    print_test("Export Markdown", exported_md is not None,
               f"Tamanho: {len(exported_md) if exported_md else 0} caracteres")
    
    # Teste 6: Listar conversas ativas
    active = interceptor.list_active_conversations()
    print_test("Listar ativas", len(active) > 0, f"Total: {len(active)}")
    
    # Teste 7: Armazenamento em DB
    messages = interceptor.get_conversation_messages(conv_id)
    print_test("Mensagens do BD", len(messages) > 0, f"Total: {len(messages)}")
    
    # Teste 8: Subscribers
    events_received = []
    def conv_subscriber(event):
        events_received.append(event)
    
    interceptor.subscribe_conversation_events(conv_subscriber)
    
    bus.publish(
        message_type=MessageType.RESPONSE,
        source="TestAgent",
        target="PythonAgent",
        content="Resposta",
        metadata={"conversation_id": conv_id}
    )
    
    time.sleep(time_sleep)
    print_test("Subscribers de conversa", len(events_received) > 0,
               f"Eventos: {len(events_received)}")
    
    # Teste 9: Finalizar conversa
    success = interceptor.finalize_conversation(conv_id)
    print_test("Finalizar conversa", success, f"Conversa movida para histórico")
    
    # Teste 10: Verificar histórico
    history = interceptor.list_conversations(limit=10)
    print_test("Histórico disponível", len(history) > 0, f"Total: {len(history)}")


def test_api_endpoints():
    """Testa endpoints da API"""
    print_header("Testing API Endpoints")
    
    try:
        import requests
        
        API_BASE = "http://localhost:8503/interceptor"
        
        # Teste 1: Conversas ativas
        try:
            response = requests.get(f"{API_BASE}/conversations/active", timeout=5)
            print_test("GET /conversations/active", response.status_code == 200,
                       f"Status: {response.status_code}")
        except Exception as e:
            print_test("GET /conversations/active", False,
                       f"Erro: {str(e)[:50]}")
        
        # Teste 2: Stats
        try:
            response = requests.get(f"{API_BASE}/stats", timeout=5)
            print_test("GET /stats", response.status_code == 200,
                       f"Status: {response.status_code}")
        except Exception as e:
            print_test("GET /stats", False,
                       f"Erro: {str(e)[:50]}")
        
        # Teste 3: Stats por fase
        try:
            response = requests.get(f"{API_BASE}/stats/by-phase", timeout=5)
            print_test("GET /stats/by-phase", response.status_code == 200,
                       f"Status: {response.status_code}")
        except Exception as e:
            print_test("GET /stats/by-phase", False,
                       f"Erro: {str(e)[:50]}")
        
        # Teste 4: Stats por agente
        try:
            response = requests.get(f"{API_BASE}/stats/by-agent", timeout=5)
            print_test("GET /stats/by-agent", response.status_code == 200,
                       f"Status: {response.status_code}")
        except Exception as e:
            print_test("GET /stats/by-agent", False,
                       f"Erro: {str(e)[:50]}")
        
        # Teste 5: Histórico
        try:
            response = requests.get(f"{API_BASE}/conversations/history", timeout=5)
            print_test("GET /conversations/history", response.status_code == 200,
                       f"Status: {response.status_code}")
        except Exception as e:
            print_test("GET /conversations/history", False,
                       f"Erro: {str(e)[:50]}")
    
    except ImportError:
        print(f"{Colors.YELLOW}⚠️  Requests não instalado - pulando testes de API{Colors.RESET}")


def test_performance():
    """Testa performance"""
    print_header("Testing Performance")
    
    import time
    bus = get_communication_bus()
    interceptor = get_agent_interceptor()
    
    # Teste 1: Throughput
    start = time.time()
    count = 1000
    
    for i in range(count):
        bus.publish(
            message_type=MessageType.LLM_CALL,
            source=f"Agent{i % 10}",
            target=f"Agent{(i+1) % 10}",
            content=f"Message {i}",
            metadata={"index": i}
        )
    
    elapsed = time.time() - start
    throughput = count / elapsed
    
    print_test("Throughput", throughput > 100,
               f"{throughput:.0f} mensagens/segundo")
    
    # Teste 2: Tamanho do buffer
    stats = bus.get_stats()
    print_test("Buffer circular", stats["buffer_size"] <= stats["buffer_max"],
               f"Tamanho: {stats['buffer_size']}/{stats['buffer_max']}")
    
    # Teste 3: Tempo de query
    start = time.time()
    messages = bus.get_messages(limit=100)
    elapsed = time.time() - start
    
    print_test("Query performance", elapsed < 0.1,
               f"Tempo: {elapsed*1000:.2f}ms para 100 mensagens")


def test_database():
    """Testa persistência em banco de dados"""
    print_header("Testing Database Persistence")
    
    interceptor = get_agent_interceptor()
    
    # Teste 1: BD foi criado
    db_path = interceptor.db_path
    print_test("Banco de dados criado", db_path.exists(),
               f"Caminho: {db_path}")
    
    # Teste 2: Tabelas criadas
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ["conversations", "messages", "conversation_snapshots"]
        all_exist = all(t in tables for t in required_tables)
        
        print_test("Tabelas necessárias", all_exist,
                   f"Tabelas: {', '.join(tables)}")
        
        # Teste 3: Índices criados
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = [row[0] for row in cursor.fetchall()]
        
        print_test("Índices criados", len(indices) > 0,
                   f"Total: {len(indices)}")
        
        conn.close()
    except Exception as e:
        print_test("Verificação de BD", False, str(e)[:50])


def test_cli():
    """Testa CLI"""
    print_header("Testing CLI")
    
    import subprocess
    
    cli_path = "specialized_agents/interceptor_cli.py"
    
    # Teste 1: Ajuda
    try:
        result = subprocess.run(
            [sys.executable, cli_path, "--help"],
            capture_output=True,
            timeout=5
        )
        print_test("CLI --help", result.returncode == 0,
                   f"Return code: {result.returncode}")
    except Exception as e:
        print_test("CLI --help", False, str(e)[:50])
    
    # Teste 2: Comando de stats
    try:
        result = subprocess.run(
            [sys.executable, cli_path, "stats", "overview"],
            capture_output=True,
            timeout=5
        )
        print_test("CLI stats overview", result.returncode == 0,
                   f"Return code: {result.returncode}")
    except Exception as e:
        print_test("CLI stats overview", False, str(e)[:50])


def test_streamlit_dashboard():
    """Testa dashboard Streamlit"""
    print_header("Testing Streamlit Dashboard")
    
    dashboard_path = "specialized_agents/conversation_monitor.py"
    
    # Verificar se arquivo existe
    from pathlib import Path
    exists = Path(dashboard_path).exists()
    print_test("Arquivo do dashboard existe", exists,
               f"Caminho: {dashboard_path}")
    
    # Verificar imports
    try:
        import streamlit
        import plotly
        import pandas
        print_test("Dependências do Streamlit", True,
                   "Todas as bibliotecas disponíveis")
    except ImportError as e:
        print_test("Dependências do Streamlit", False,
                   f"Faltando: {str(e)}")


def main():
    """Executa toda suite de testes"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════╗")
    print("║  Agent Conversation Interceptor - Test Suite          ║")
    print("║  Validação completa do sistema de interceptação       ║")
    print("╚════════════════════════════════════════════════════════╝")
    print(Colors.RESET)
    
    tests = [
        ("Communication Bus", test_communication_bus),
        ("Interceptor", test_interceptor),
        ("Performance", test_performance),
        ("Database", test_database),
        ("CLI", test_cli),
        ("Streamlit Dashboard", test_streamlit_dashboard),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            test_func()
            results[test_name] = "✅"
        except Exception as e:
            print(f"\n{Colors.RED}❌ Erro em {test_name}:{Colors.RESET}")
            print(f"   {str(e)}")
            results[test_name] = "❌"
    
    # Resumo
    print_header("Resumo dos Testes")
    
    passed = sum(1 for v in results.values() if v == "✅")
    total = len(results)
    
    for test_name, result in results.items():
        print(f"{result} {test_name}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} categorias passaram{Colors.RESET}\n")
    
    if passed == total:
        print(f"{Colors.GREEN}✅ Todos os testes passaram!{Colors.RESET}\n")
        return 0
    else:
        print(f"{Colors.YELLOW}⚠️  Alguns testes falharam - verificar detalhes acima{Colors.RESET}\n")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
