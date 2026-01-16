#!/usr/bin/env python3
"""
Dashboard de Interceptação de Conversas em Tempo Real
Interface Streamlit para monitorar conversas entre agentes
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import time
from pathlib import Path
import sys

# Adicionar path
sys.path.insert(0, str(Path(__file__).parent))

from agent_interceptor import get_agent_interceptor, ConversationPhase
from agent_communication_bus import get_communication_bus

# Configuração da página
st.set_page_config(
    page_title="🔍 Interceptor de Conversas",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    /* Estilo geral */
    .main {
        background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%);
    }
    
    /* Cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    /* Conversation item */
    .conversation-item {
        background: #1a202c;
        border-left: 4px solid #38b2ac;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .conversation-item:hover {
        border-left-color: #48bb78;
        transform: translateX(5px);
        box-shadow: 0 4px 10px rgba(56, 178, 172, 0.2);
    }
    
    /* Message */
    .message-item {
        background: #2d3748;
        padding: 12px;
        margin: 8px 0;
        border-radius: 5px;
        border-left: 3px solid #667eea;
        font-family: monospace;
        font-size: 0.85em;
    }
    
    .message-item.error {
        border-left-color: #f56565;
    }
    
    .message-item.success {
        border-left-color: #48bb78;
    }
    
    /* Phase badge */
    .phase-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: bold;
        margin: 5px 5px 5px 0;
    }
    
    .phase-initiated { background: #4299e1; color: white; }
    .phase-analyzing { background: #ed8936; color: white; }
    .phase-planning { background: #9f7aea; color: white; }
    .phase-coding { background: #38b2ac; color: white; }
    .phase-testing { background: #ecc94b; color: #1a202c; }
    .phase-deploying { background: #48bb78; color: white; }
    .phase-completed { background: #22863a; color: white; }
    .phase-failed { background: #cb2431; color: white; }
</style>
""", unsafe_allow_html=True)

# Inicializar estado
if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 2
if "selected_conversation" not in st.session_state:
    st.session_state.selected_conversation = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True


def format_duration(seconds: float) -> str:
    """Formata duração em texto legível"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def get_phase_badge(phase: str) -> str:
    """Retorna badge HTML para fase"""
    phase_lower = phase.lower()
    return f'<span class="phase-badge phase-{phase_lower}">{phase.upper()}</span>'


def get_interceptor():
    """Obtém instância do interceptador"""
    return get_agent_interceptor()


def get_bus():
    """Obtém instância do bus"""
    return get_communication_bus()


# Sidebar
st.sidebar.title("⚙️ Configurações")

# Auto-refresh
st.session_state.auto_refresh = st.sidebar.checkbox(
    "🔄 Auto-refresh", 
    value=st.session_state.auto_refresh
)

if st.session_state.auto_refresh:
    refresh_options = {
        "1 segundo": 1,
        "2 segundos": 2,
        "5 segundos": 5,
        "10 segundos": 10,
    }
    refresh_key = st.sidebar.select_slider(
        "Intervalo de refresh",
        options=list(refresh_options.keys()),
        value="2 segundos"
    )
    st.session_state.refresh_interval = refresh_options[refresh_key]

# Filtros
st.sidebar.markdown("---")
st.sidebar.title("🔍 Filtros")

filter_agent = st.sidebar.text_input("Filtrar por agente", placeholder="ex: PythonAgent")
filter_phase = st.sidebar.selectbox(
    "Filtrar por fase",
    ["Todas", "INITIATED", "ANALYZING", "PLANNING", "CODING", "TESTING", "DEPLOYING", "COMPLETED", "FAILED"]
)

# Main content
st.title("🔍 Interceptor de Conversas entre Agentes")
st.markdown("Sistema de interceptação, análise e visualização em tempo real de conversas entre agentes")

# Obter dados
interceptor = get_interceptor()
bus = get_bus()

# Estatísticas gerais
col1, col2, col3, col4, col5 = st.columns(5)

stats = interceptor.get_stats()

with col1:
    st.metric(
        "📊 Total de Mensagens",
        f"{stats['total_messages_intercepted']:,}",
        f"+{stats['total_messages_intercepted']}"
    )

with col2:
    st.metric(
        "🔄 Conversas Ativas",
        stats['active_conversations'],
        delta=None
    )

with col3:
    st.metric(
        "✅ Conversas Completadas",
        stats['total_conversations'],
        delta=None
    )

with col4:
    bus_stats = bus.get_stats()
    st.metric(
        "📨 Buffer do Bus",
        f"{bus_stats['buffer_size']}/{bus_stats['buffer_max']}",
        delta=None
    )

with col5:
    uptime_hours = stats['uptime_seconds'] / 3600
    st.metric(
        "⏱️ Uptime",
        f"{uptime_hours:.1f}h",
        delta=None
    )

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔴 Conversas Ativas",
    "📊 Análise",
    "💬 Histórico",
    "📈 Métricas",
    "⚡ Tempo Real"
])

# TAB 1: Conversas Ativas
with tab1:
    st.subheader("Conversas em Andamento")
    
    active_convs = interceptor.list_active_conversations()
    
    if not active_convs:
        st.info("Nenhuma conversa ativa no momento")
    else:
        # Filtrar
        if filter_phase != "Todas":
            active_convs = [c for c in active_convs if c["phase"].upper() == filter_phase]
        
        if filter_agent:
            active_convs = [
                c for c in active_convs
                if any(filter_agent.lower() in p.lower() for p in c["participants"])
            ]
        
        for conv in active_convs:
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                phase_html = get_phase_badge(conv["phase"])
                st.markdown(
                    f"""
                    **Conversa ID:** {conv['id'][:20]}...
                    
                    {phase_html}
                    
                    **Participantes:** {", ".join(conv['participants'])}
                    """,
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric("Mensagens", conv["message_count"])
            
            with col3:
                st.metric("Duração", format_duration(conv["duration_seconds"]))
            
            with col4:
                if st.button("📋 Detalhes", key=f"details_{conv['id']}"):
                    st.session_state.selected_conversation = conv["id"]

# TAB 2: Análise Detalhada
with tab2:
    st.subheader("Análise de Conversa Selecionada")
    
    # Seletor de conversa
    active_convs = interceptor.list_active_conversations()
    conv_options = {
        f"{c['id'][:15]}... ({', '.join(c['participants'])})": c['id']
        for c in active_convs
    }
    
    if conv_options:
        selected_conv_display = st.selectbox(
            "Selecione conversa para análise",
            options=list(conv_options.keys())
        )
        selected_conv_id = conv_options[selected_conv_display]
        
        # Análise
        analysis = interceptor.analyze_conversation(selected_conv_id)
        
        if analysis:
            # Resumo
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total de Mensagens", analysis["summary"]["total_messages"])
            with col2:
                st.metric("Duração", format_duration(analysis["summary"]["duration_seconds"]))
            with col3:
                st.metric("Participantes", len(analysis["summary"]["participants"]))
            with col4:
                st.metric("Fase", analysis["summary"]["phase"])
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            # Tipo de mensagem
            with col1:
                msg_types_df = pd.DataFrame([
                    {"Tipo": k, "Quantidade": v}
                    for k, v in analysis["message_types"].items()
                ])
                if not msg_types_df.empty:
                    fig = px.bar(msg_types_df, x="Tipo", y="Quantidade", title="Distribuição de Tipos")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Distribuição de origem
            with col2:
                source_df = pd.DataFrame([
                    {"Agente": k, "Mensagens": v}
                    for k, v in analysis["source_distribution"].items()
                ])
                if not source_df.empty:
                    fig = px.pie(source_df, values="Mensagens", names="Agente", title="Distribuição por Agente")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Mensagens
            st.markdown("---")
            st.subheader("💬 Mensagens")
            
            messages = interceptor.get_conversation_messages(selected_conv_id)
            
            for msg in messages[-20:]:  # Últimas 20
                msg_type_lower = msg["message_type"].lower()
                css_class = "error" if "error" in msg_type_lower else "success" if "complete" in msg_type_lower else ""
                
                st.markdown(
                    f"""
                    <div class="message-item {css_class}">
                    <strong>[{msg['timestamp']}] {msg['message_type'].upper()}</strong><br>
                    {msg['source']} → {msg['target']}<br>
                    <pre>{msg['content'][:500]}{'...' if len(msg['content']) > 500 else ''}</pre>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        st.info("Nenhuma conversa ativa disponível")

# TAB 3: Histórico
with tab3:
    st.subheader("Histórico de Conversas")
    
    limit = st.slider("Número de conversas", 10, 100, 50)
    
    convs = interceptor.list_conversations(limit=limit)
    
    if convs:
        # DataFrame
        df = pd.DataFrame(convs)
        df["started_at"] = pd.to_datetime(df["started_at"])
        df["duration_min"] = (df["duration_seconds"] / 60).round(2)
        
        # Exibir tabela
        st.dataframe(
            df[["id", "phase", "message_count", "duration_min"]].rename({
                "id": "Conversa ID",
                "phase": "Fase",
                "message_count": "Mensagens",
                "duration_min": "Duração (min)"
            }),
            use_container_width=True
        )
        
        # Gráfico de fases
        phase_counts = df["phase"].value_counts()
        fig = px.bar(
            x=phase_counts.index,
            y=phase_counts.values,
            title="Conversas por Fase",
            labels={"x": "Fase", "y": "Quantidade"}
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma conversa no histórico")

# TAB 4: Métricas Avançadas
with tab4:
    st.subheader("📈 Métricas e Estatísticas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Taxa de Mensagens/min", 
                  f"{stats.get('messages_per_minute', 0):.2f}")
    
    with col2:
        if stats['total_conversations'] > 0:
            avg_duration = stats.get('average_duration', 0)
            st.metric("Duração Média (s)", f"{avg_duration:.1f}")
    
    with col3:
        st.metric("Taxa de Erro", 
                  f"{(stats['errors'] / max(stats['total_messages_intercepted'], 1)) * 100:.2f}%")
    
    # Gráfico de linha - mensagens ao longo do tempo
    st.markdown("---")
    
    messages_over_time = bus.get_messages(limit=1000)
    if messages_over_time:
        timestamps = [m.timestamp for m in messages_over_time]
        times_data = pd.DataFrame({
            "Timestamp": timestamps,
            "Cumulative": range(1, len(timestamps) + 1)
        })
        
        fig = px.line(times_data, x="Timestamp", y="Cumulative", 
                      title="Mensagens Ao Longo do Tempo",
                      labels={"Cumulative": "Total Cumulativo"})
        st.plotly_chart(fig, use_container_width=True)

# TAB 5: Tempo Real
with tab5:
    st.subheader("⚡ Monitor em Tempo Real")
    
    # Espaço para atualizações
    placeholder = st.empty()
    status_placeholder = st.empty()
    
    if st.session_state.auto_refresh:
        # Atualizar automaticamente
        while True:
            with placeholder.container():
                st.markdown("### Últimas Mensagens")
                
                messages = bus.get_messages(limit=20)
                
                if messages:
                    for msg in reversed(messages[-10:]):
                        st.markdown(f"""
                        **[{msg.timestamp.strftime('%H:%M:%S')}]** `{msg.message_type.value}`
                        
                        **{msg.source}** → **{msg.target}**
                        ```
                        {msg.content[:300]}{'...' if len(msg.content) > 300 else ''}
                        ```
                        """)
                else:
                    st.info("Aguardando mensagens...")
            
            with status_placeholder.container():
                bus_stats = bus.get_stats()
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Buffer", f"{bus_stats['buffer_size']}/{bus_stats['buffer_max']}")
                with col2:
                    st.metric("Msgs/min", f"{bus_stats.get('messages_per_minute', 0):.1f}")
                with col3:
                    st.metric("Status", "🟢 Ativo" if bus_stats['recording'] else "🔴 Pausado")
            
            time.sleep(st.session_state.refresh_interval)
    else:
        st.info("Auto-refresh desabilitado - clique no botão acima para ativar")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #718096; font-size: 0.85em;">
    🔍 Agent Conversation Interceptor v1.0 | Sistema de Interceptação em Tempo Real
    </div>
    """,
    unsafe_allow_html=True
)
