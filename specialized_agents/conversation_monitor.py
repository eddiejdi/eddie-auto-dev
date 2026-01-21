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
import os


# Adicionar root do projeto ao path para permitir imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent))

from specialized_agents.agent_interceptor import get_agent_interceptor, ConversationPhase
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

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
    
    /* Simple stacked conversation boxes */
    .conv-box {
        background: #f7fafc;
        color: #1a202c;
        border: 1px solid #e2e8f0;
        padding: 10px 12px;
        margin: 8px 0;
        border-radius: 6px;
        font-family: Arial, Helvetica, sans-serif;
        font-size: 0.95em;
    }

    .conv-title { font-weight: bold; margin-bottom: 6px; }
    .conv-meta { color: #4a5568; font-size: 0.85em; margin-bottom: 8px; }
    .conv-preview { background: #ffffff; border: 1px solid #edf2f7; padding: 8px; border-radius: 4px; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

# Inicializar estado
if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 2
if "selected_conversation" not in st.session_state:
    st.session_state.selected_conversation = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True

# Inicializar interceptor e bus cedo para evitar referências antes da inicialização
# Usar as funções importadas diretamente para evitar chamar os wrappers antes
# de sua definição no arquivo.
try:
    interceptor = get_agent_interceptor()
except Exception as e:
    print(f"[dashboard] Falha ao inicializar interceptor: {e}")
    interceptor = None

try:
    bus = get_communication_bus()
except Exception as e:
    print(f"[dashboard] Falha ao inicializar bus: {e}")
    bus = None


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


def _normalize_message(msg) -> Dict[str, Any]:
    """Retorna uma dict normalizada para message (timestamp, message_type, source, target, content).
    Aceita tanto objetos com atributos quanto dicts retornados por diferentes implementações.
    """
    if isinstance(msg, dict):
        ts = msg.get("timestamp")
        # support both 'message_type' and 'type' keys
        mt = msg.get("message_type") or msg.get("type")
        source = msg.get("source")
        target = msg.get("target")
        content = msg.get("content") or msg.get("content")
    else:
        ts = getattr(msg, "timestamp", None)
        mt = getattr(msg, "message_type", None)
        source = getattr(msg, "source", None)
        target = getattr(msg, "target", None)
        content = getattr(msg, "content", None)

    # Normalize message_type to string
    if mt is None:
        mt_str = "UNKNOWN"
    elif isinstance(mt, str):
        mt_str = mt
    elif hasattr(mt, "value"):
        mt_str = str(mt.value)
    else:
        mt_str = str(mt)

    return {
        "timestamp": ts,
        "message_type": mt_str,
        "source": source,
        "target": target,
        "content": content,
    }


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
# Phase filter stored in session_state so it can be updated from buttons
if "filter_phase" not in st.session_state:
    st.session_state.filter_phase = "Todas"

st.sidebar.selectbox(
    "Filtrar por fase",
    ["Todas", "INITIATED", "ANALYZING", "PLANNING", "CODING", "TESTING", "DEPLOYING", "COMPLETED", "FAILED"],
    key="filter_phase",
    label_visibility="collapsed"
)

# Local alias for convenience
filter_phase = st.session_state.get("filter_phase", "Todas")

# Botão para iniciar conversa de teste manualmente
def start_test_conversation(bus):
    import time
    conv_id = "ui_test_conv_" + time.strftime('%Y%m%d%H%M%S')
    # Publicar mensagem inicial
    bus.publish(
        message_type=MessageType.REQUEST,
        source="UIManualAgent",
        target="TestAgent",
        content="Conversa iniciada via botão de teste",
        metadata={"conversation_id": conv_id}
    )
    # Publicar algumas mensagens adicionais
    for i in range(3):
        bus.publish(
            message_type=MessageType.LLM_CALL,
            source="PythonAgent",
            target="TestAgent",
            content=f"Mensagem de teste {i}",
            metadata={"conversation_id": conv_id}
        )
    # Log to stdout so it appears in Streamlit logs for diagnostics
    try:
        print(f"[dashboard] Created UI test conversation: {conv_id}")
    except Exception:
        pass
    return conv_id


# Auto-create a UI test conversation on first load when requested via env var
if os.environ.get("AUTO_CREATE_UI_TEST_CONV") == "1":
    if not st.session_state.get("ui_test_created"):
        try:
            created = start_test_conversation(get_bus())
            st.session_state.ui_test_created = created
            st.sidebar.success(f"Conversa criada automaticamente: {created}")
        except Exception as e:
            print(f"[dashboard] Auto-create failed: {e}")

if st.sidebar.button("▶️ Iniciar conversa de teste"):
    # Garantir que o bus esteja disponível no momento do clique
    if bus is None:
        bus = get_bus()
    created_id = start_test_conversation(bus)
    st.sidebar.success(f"Conversa de teste criada: {created_id}")
    st.session_state.selected_conversation = created_id

# Main content
st.title("🔍 Interceptor de Conversas entre Agentes")
st.markdown("Sistema de interceptação, análise e visualização em tempo real de conversas entre agentes")

# Obter dados (variáveis já inicializadas no topo)
if interceptor is None:
    interceptor = get_interceptor()
if bus is None:
    bus = get_bus()

# NOTE: removed in-process auto-create behavior to comply with project rules.

# NOTE: removed in-process test endpoint to comply with project rules.

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

    # Se não houver conversas ativas em memória, tentar recuperar histórico recente do DB
    if not active_convs:
        recent = interceptor.list_conversations(limit=10, include_active=False)
        if recent:
            # transformar o formato do histórico para compatibilidade com a UI de 'active_convs'
            active_convs = [
                {
                    "id": c.get("id") or c.get("conversation_id"),
                    "started_at": c.get("started_at"),
                    "participants": c.get("participants", []),
                    "message_count": c.get("message_count", len(c.get("messages", []))),
                    "phase": c.get("phase", "active"),
                    "duration_seconds": c.get("duration_seconds", 0),
                }
                for c in recent
            ]

    # Se ainda não houver conversas (nem em memória nem no DB)
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
            # Build a small preview for the conversation (last message)
            preview = ""
            try:
                msgs = interceptor.get_conversation_messages(conv["id"]) or []
                if msgs:
                    nm = _normalize_message(msgs[-1])
                    preview = (nm.get("content") or "")[:400]
            except Exception:
                preview = ""

            phase_html = get_phase_badge(conv["phase"])
            participants = ", ".join(conv.get("participants", []))

            st.markdown(
                f"""
                <div class="conv-box">
                  <div class="conv-title">Conversa ID: {conv['id'][:20]}... {phase_html}</div>
                  <div class="conv-meta">Participantes: {participants} | Mensagens: {conv['message_count']} | Duração: {format_duration(conv['duration_seconds'])}</div>
                  <div class="conv-preview">{preview}{'...' if len(preview) >= 400 else ''}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Small action buttons per conversation
            if st.button(f"Filtrar: {conv['phase'].upper()}", key=f"filter_phase_{conv['id']}"):
                st.session_state.filter_phase = conv['phase'].upper()

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
                nm = _normalize_message(msg)
                mt = nm.get("message_type", "UNKNOWN")
                msg_type_lower = mt.lower()
                css_class = "error" if "error" in msg_type_lower else "success" if "complete" in msg_type_lower else ""

                ts = nm.get("timestamp")
                try:
                    ts_display = pd.to_datetime(ts).isoformat()
                except Exception:
                    ts_display = str(ts)

                st.markdown(
                    f"""
                    <div class="message-item {css_class}">
                    <strong>[{ts_display}] {mt.upper()}</strong><br>
                    {nm.get('source','-')} → {nm.get('target','-')}<br>
                    <pre>{(nm.get('content') or '')[:500]}{'...' if len((nm.get('content') or '')) > 500 else ''}</pre>
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
        total_msgs = stats.get('total_messages_intercepted', 0)
        errors = stats.get('errors', 0)
        error_rate = (errors / max(total_msgs, 1)) * 100
        st.metric("Taxa de Erro", f"{error_rate:.2f}%")
    
    # Gráfico de linha - mensagens ao longo do tempo
    st.markdown("---")
    
    messages_over_time = bus.get_messages(limit=1000)
    if messages_over_time:
        timestamps = [_normalize_message(m)["timestamp"] for m in messages_over_time]
        times_data = pd.DataFrame({
            "Timestamp": pd.to_datetime(timestamps),
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
                        nm = _normalize_message(msg)
                        ts = nm["timestamp"]
                        try:
                            ts_str = pd.to_datetime(ts).strftime('%H:%M:%S')
                        except Exception:
                            ts_str = str(ts)
                        mtype = nm.get("message_type", "UNKNOWN")
                        source = nm.get("source", "-")
                        target = nm.get("target", "-")
                        content = nm.get("content", "") or ""

                        st.markdown(f"""
                        **[{ts_str}]** `{mtype}`
                        
                        **{source}** → **{target}**
                        ```
                        {content[:300]}{'...' if len(content) > 300 else ''}
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
