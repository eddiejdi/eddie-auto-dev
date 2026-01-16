#!/usr/bin/env python3
"""
CLI para Interceptador de Conversas
Interface de linha de comando para monitorar e gerenciar conversas interceptadas
"""
import click
import requests
import json
import tabulate
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional, List, Dict, Any
import time

# Configuração
API_BASE = "http://localhost:8503/interceptor"
COLORS = {
    "success": "\033[92m",      # Green
    "error": "\033[91m",        # Red
    "warning": "\033[93m",      # Yellow
    "info": "\033[94m",         # Blue
    "reset": "\033[0m",
    "bold": "\033[1m"
}


def print_colored(message: str, color: str = "info"):
    """Imprime mensagem colorida"""
    print(f"{COLORS[color]}{message}{COLORS['reset']}")


def print_table(data: List[Dict[str, Any]], headers: Optional[List[str]] = None):
    """Imprime tabela formatada"""
    if not data:
        print_colored("Nenhum dado disponível", "warning")
        return
    
    if headers is None:
        headers = "keys"
    
    print(tabulate.tabulate(data, headers=headers, tablefmt="grid"))


@click.group()
def cli():
    """🔍 Interceptador de Conversas - CLI"""
    pass


# ============================================================================
# CONVERSAS
# ============================================================================

@cli.group()
def conversations():
    """Gerenciar conversas"""
    pass


@conversations.command()
@click.option("--agent", help="Filtrar por agente")
@click.option("--phase", help="Filtrar por fase")
def active(agent: Optional[str], phase: Optional[str]):
    """Listar conversas ativas"""
    try:
        params = {}
        if agent:
            params["agent"] = agent
        if phase:
            params["phase"] = phase
        
        response = requests.get(f"{API_BASE}/conversations/active", params=params)
        response.raise_for_status()
        
        data = response.json()
        convs = data.get("conversations", [])
        
        if convs:
            table_data = []
            for conv in convs:
                table_data.append({
                    "ID": conv["id"][:20] + "...",
                    "Fase": conv["phase"],
                    "Participantes": ", ".join(conv["participants"]),
                    "Mensagens": conv["message_count"],
                    "Duração": f"{conv['duration_seconds']:.1f}s"
                })
            
            print_colored(f"\n✅ {data['count']} conversa(s) ativa(s)\n", "success")
            print_table(table_data)
        else:
            print_colored("Nenhuma conversa ativa", "warning")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@conversations.command()
@click.argument("conversation_id")
def info(conversation_id: str):
    """Informações detalhadas de uma conversa"""
    try:
        response = requests.get(f"{API_BASE}/conversations/{conversation_id}")
        response.raise_for_status()
        
        data = response.json()["conversation"]
        
        print_colored(f"\n📋 Conversa: {conversation_id}\n", "info")
        print(f"{'Iniciada em:':<20} {data['started_at']}")
        print(f"{'Finalizada em:':<20} {data['ended_at']}")
        print(f"{'Fase:':<20} {data['phase']}")
        print(f"{'Participantes:':<20} {', '.join(data['participants'])}")
        print(f"{'Total de Mensagens:':<20} {data['message_count']}")
        print(f"{'Duração:':<20} {data['duration_seconds']:.2f}s")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@conversations.command()
@click.argument("conversation_id")
@click.option("--limit", default=20, help="Número de mensagens")
@click.option("--type", help="Filtrar por tipo")
def messages(conversation_id: str, limit: int, type: Optional[str]):
    """Listar mensagens de uma conversa"""
    try:
        params = {"limit": limit}
        if type:
            params["message_type"] = type
        
        response = requests.get(
            f"{API_BASE}/conversations/{conversation_id}/messages",
            params=params
        )
        response.raise_for_status()
        
        data = response.json()
        msgs = data.get("messages", [])
        
        if msgs:
            print_colored(f"\n💬 {data['count']} mensagem(ns)\n", "info")
            
            for msg in msgs[-limit:]:
                print_colored(f"[{msg['timestamp']}] {msg['message_type'].upper()}", "bold")
                print(f"  {msg['source']} → {msg['target']}")
                content = msg['content'][:100]
                if len(msg['content']) > 100:
                    content += "..."
                print(f"  {content}\n")
        else:
            print_colored("Nenhuma mensagem encontrada", "warning")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@conversations.command()
@click.argument("conversation_id")
def analyze(conversation_id: str):
    """Analisar conversa"""
    try:
        response = requests.get(f"{API_BASE}/conversations/{conversation_id}/analysis")
        response.raise_for_status()
        
        analysis = response.json()["analysis"]
        
        print_colored(f"\n📊 Análise: {conversation_id}\n", "info")
        
        # Resumo
        summary = analysis["summary"]
        print(f"{'Participantes:':<25} {', '.join(summary['participants'])}")
        print(f"{'Total de Mensagens:':<25} {summary['total_messages']}")
        print(f"{'Duração:':<25} {summary['duration_seconds']:.2f}s")
        print(f"{'Fase:':<25} {summary['phase']}\n")
        
        # Tipos de mensagem
        print(f"{'Tipos de Mensagem:':<25}")
        for msg_type, count in analysis["message_types"].items():
            print(f"  • {msg_type}: {count}")
        
        print()
        
        # Distribuição de origem
        print(f"{'Distribuição por Agente:':<25}")
        for agent, count in analysis["source_distribution"].items():
            print(f"  • {agent}: {count}")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@conversations.command()
@click.option("--limit", default=50, help="Número de conversas")
@click.option("--agent", help="Filtrar por agente")
@click.option("--phase", help="Filtrar por fase")
@click.option("--hours", type=int, help="Últimas N horas")
def history(limit: int, agent: Optional[str], phase: Optional[str], hours: Optional[int]):
    """Listar histórico de conversas"""
    try:
        params = {"limit": limit}
        if agent:
            params["agent"] = agent
        if phase:
            params["phase"] = phase
        if hours:
            params["since_hours"] = hours
        
        response = requests.get(f"{API_BASE}/conversations/history", params=params)
        response.raise_for_status()
        
        data = response.json()
        convs = data.get("conversations", [])
        
        if convs:
            table_data = []
            for conv in convs:
                table_data.append({
                    "ID": conv["id"][:15] + "...",
                    "Fase": conv["phase"],
                    "Participantes": ", ".join(conv["participants"][:2]),
                    "Mensagens": conv["message_count"],
                    "Duração (s)": f"{conv['duration_seconds']:.1f}"
                })
            
            print_colored(f"\n📜 {data['count']} conversa(s) encontrada(s)\n", "success")
            print_table(table_data)
        else:
            print_colored("Nenhuma conversa encontrada", "warning")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@conversations.command()
@click.argument("conversation_id")
@click.option("--format", type=click.Choice(["json", "markdown", "text"]), default="json")
def export(conversation_id: str, format: str):
    """Exportar conversa"""
    try:
        response = requests.get(
            f"{API_BASE}/conversations/{conversation_id}/export",
            params={"format": format}
        )
        response.raise_for_status()
        
        data = response.json()
        content = data["content"]
        
        # Salvar em arquivo
        filename = f"conversation_{conversation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        with open(filename, "w") as f:
            f.write(content)
        
        print_colored(f"✅ Conversa exportada para {filename}", "success")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


# ============================================================================
# ESTATÍSTICAS
# ============================================================================

@cli.group()
def stats():
    """Ver estatísticas"""
    pass


@stats.command()
def overview():
    """Visão geral de estatísticas"""
    try:
        response = requests.get(f"{API_BASE}/stats")
        response.raise_for_status()
        
        data = response.json()
        interceptor = data["interceptor"]
        bus = data["communication_bus"]
        
        print_colored(f"\n📈 Estatísticas Gerais\n", "info")
        
        print(f"{'Total de Mensagens:':<30} {interceptor['total_messages_intercepted']:,}")
        print(f"{'Conversas Ativas:':<30} {interceptor['active_conversations']}")
        print(f"{'Conversas Completadas:':<30} {interceptor['total_conversations']}")
        print(f"{'Taxa de Erro:':<30} {interceptor['errors']}")
        print(f"{'Uptime:':<30} {interceptor['uptime_seconds']:.1f}s")
        print()
        
        print(f"{'Buffer do Bus:':<30} {bus['buffer_size']}/{bus['buffer_max']}")
        print(f"{'Taxa de Mensagens/min:':<30} {bus.get('messages_per_minute', 0):.2f}")
        print(f"{'Status:':<30} {'🟢 Ativo' if bus['recording'] else '🔴 Pausado'}")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@stats.command()
def by_phase():
    """Estatísticas por fase"""
    try:
        response = requests.get(f"{API_BASE}/stats/by-phase")
        response.raise_for_status()
        
        data = response.json()["by_phase"]
        
        print_colored(f"\n📊 Por Fase\n", "info")
        
        table_data = []
        for phase, stats_data in data.items():
            table_data.append({
                "Fase": phase,
                "Conversas": stats_data["count"],
                "Duração Média (s)": f"{stats_data['avg_duration']:.1f}",
                "Msgs Médias": f"{stats_data['avg_messages']:.0f}"
            })
        
        print_table(table_data)
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@stats.command()
def by_agent():
    """Estatísticas por agente"""
    try:
        response = requests.get(f"{API_BASE}/stats/by-agent")
        response.raise_for_status()
        
        data = response.json()["by_agent"]
        
        print_colored(f"\n🤖 Por Agente\n", "info")
        
        table_data = []
        for agent, agent_stats in data.items():
            table_data.append({
                "Agente": agent,
                "Enviadas": agent_stats["sent"],
                "Recebidas": agent_stats["received"],
                "Total": agent_stats["sent"] + agent_stats["received"]
            })
        
        print_table(sorted(table_data, key=lambda x: x["Total"], reverse=True))
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


# ============================================================================
# CONTROLE
# ============================================================================

@cli.group()
def control():
    """Controlar gravação e filtros"""
    pass


@control.command()
def pause():
    """Pausar gravação"""
    try:
        response = requests.post(f"{API_BASE}/recording/pause")
        response.raise_for_status()
        
        print_colored("✅ Gravação pausada", "success")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@control.command()
def resume():
    """Retomar gravação"""
    try:
        response = requests.post(f"{API_BASE}/recording/resume")
        response.raise_for_status()
        
        print_colored("✅ Gravação retomada", "success")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@control.command()
def clear():
    """Limpar buffer"""
    try:
        if click.confirm("Tem certeza que deseja limpar o buffer?"):
            response = requests.post(f"{API_BASE}/recording/clear")
            response.raise_for_status()
            
            print_colored("✅ Buffer limpo", "success")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


# ============================================================================
# BUSCA
# ============================================================================

@cli.group()
def search():
    """Buscar conversas"""
    pass


@search.command()
@click.argument("query")
@click.option("--limit", default=20)
def content(query: str, limit: int):
    """Buscar por conteúdo"""
    try:
        response = requests.get(
            f"{API_BASE}/search/by-content",
            params={"query": query, "limit": limit}
        )
        response.raise_for_status()
        
        data = response.json()
        
        print_colored(f"\n🔎 {data['matches']} resultado(s) para '{query}'\n", "info")
        
        for conv_id, messages in data["conversations"].items():
            print_colored(f"📌 Conversa: {conv_id[:20]}...", "bold")
            print(f"   Mensagens encontradas: {len(messages)}\n")
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@search.command()
@click.argument("agent")
def agent(agent: str):
    """Buscar por agente"""
    try:
        response = requests.get(f"{API_BASE}/search/by-agent", params={"agent": agent})
        response.raise_for_status()
        
        data = response.json()
        convs = data.get("conversations", [])
        
        print_colored(f"\n🤖 {data['count']} conversa(s) do agente '{agent}'\n", "info")
        
        table_data = []
        for conv in convs:
            table_data.append({
                "ID": conv["id"][:15] + "...",
                "Fase": conv["phase"],
                "Mensagens": conv["message_count"],
                "Duração": f"{conv['duration_seconds']:.1f}s"
            })
        
        print_table(table_data)
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


@search.command()
@click.argument("phase")
def phase(phase: str):
    """Buscar por fase"""
    try:
        response = requests.get(f"{API_BASE}/search/by-phase", params={"phase": phase})
        response.raise_for_status()
        
        data = response.json()
        convs = data.get("conversations", [])
        
        print_colored(f"\n📊 {data['count']} conversa(s) na fase '{phase}'\n", "info")
        
        table_data = []
        for conv in convs:
            table_data.append({
                "ID": conv["id"][:15] + "...",
                "Participantes": ", ".join(conv["participants"][:2]),
                "Mensagens": conv["message_count"],
                "Duração": f"{conv['duration_seconds']:.1f}s"
            })
        
        print_table(table_data)
    
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


# ============================================================================
# MONITOR TEMPO REAL
# ============================================================================

@cli.command()
@click.option("--interval", default=2, help="Intervalo de refresh em segundos")
def monitor(interval: int):
    """Monitor em tempo real"""
    try:
        while True:
            response = requests.get(f"{API_BASE}/stats")
            response.raise_for_status()
            
            data = response.json()
            interceptor = data["interceptor"]
            bus = data["communication_bus"]
            
            # Limpar tela
            print("\033[2J\033[H", end="")
            
            print_colored("🔍 INTERCEPTOR DE CONVERSAS - MONITOR TEMPO REAL", "bold")
            print(f"Atualizado em: {data['timestamp']}\n")
            
            print(f"📊 Mensagens: {interceptor['total_messages_intercepted']:,} | " +
                  f"🔴 Ativas: {interceptor['active_conversations']} | " +
                  f"✅ Completadas: {interceptor['total_conversations']}\n")
            
            print(f"Buffer: {bus['buffer_size']}/{bus['buffer_max']} | " +
                  f"Taxa: {bus.get('messages_per_minute', 0):.1f} msg/min | " +
                  f"Status: {'🟢 Ativo' if bus['recording'] else '🔴 Pausado'}\n")
            
            # Conversas ativas
            active = interceptor.get("active_conversations_list", [])
            if active:
                print_colored("📌 Conversas Ativas:", "bold")
                for conv in active[:5]:
                    print(f"  • {conv['participants']} | Fase: {conv['phase']} | " +
                          f"Msgs: {conv['message_count']} | Duração: {conv['duration_seconds']:.1f}s")
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print_colored("\n✅ Monitor finalizado", "success")
    except requests.exceptions.RequestException as e:
        print_colored(f"❌ Erro: {e}", "error")


if __name__ == "__main__":
    cli()
