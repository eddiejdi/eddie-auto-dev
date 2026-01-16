#!/usr/bin/env python3
"""
Interface Simples e Minimalista para Visualizar Conversas dos Agentes
Textbox rolante com suporte a filtros básicos
"""
import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
from pathlib import Path
import sys
import os
from threading import Thread

# Adicionar path do projeto raiz
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)
os.chdir(project_root)

# Import usando path absoluto
from specialized_agents.agent_interceptor import get_agent_interceptor

# Configuração da página
st.set_page_config(
    page_title="💬 Conversas Simples",
    page_icon="💬",
    layout="wide"
)

# CSS minimalista
st.markdown("""
<style>
    body {
        background-color: #0a0e27;
        color: #e0e0e0;
    }
    
    .main {
        padding: 20px;
    }
    
    .conversation-box {
        background-color: #1a1f3a;
        border: 1px solid #2d3561;
        border-radius: 8px;
        padding: 15px;
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 13px;
        line-height: 1.6;
        max-height: 700px;
        overflow-y: auto;
        color: #e0e0e0;
    }
    
    .message-sender {
        color: #48d1cc;
        font-weight: bold;
    }
    
    .message-timestamp {
        color: #888;
        font-size: 11px;
    }
    
    .message-error {
        color: #ff6b6b;
    }
    
    .message-success {
        color: #51cf66;
    }
    
    .message-info {
        color: #74c0fc;
    }
    
    .message-warning {
        color: #ffd93d;
    }
    
    .divider {
        color: #2d3561;
        margin: 10px 0;
    }
    
    .control-panel {
        background-color: #1a1f3a;
        border: 1px solid #2d3561;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 20px;
    }
    
    .stat-badge {
        display: inline-block;
        background-color: #2d3561;
        padding: 8px 12px;
        border-radius: 5px;
        margin-right: 10px;
        margin-bottom: 10px;
        font-size: 12px;
    }
    
    .stat-badge-active {
        background-color: #48d1cc;
        color: #0a0e27;
    }
    
    .stat-badge-completed {
        background-color: #51cf66;
        color: #0a0e27;
    }
    
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1a1f3a;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #2d3561;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #48d1cc;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_interceptor():
    """Obter instância do interceptor"""
    return get_agent_interceptor()

def format_message(message: Dict[str, Any]) -> str:
    """Formatar mensagem para exibição"""
    timestamp = message.get("timestamp", "")
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            timestamp_str = dt.strftime("%H:%M:%S")
        except:
            timestamp_str = timestamp[-8:] if len(timestamp) > 8 else timestamp
    else:
        timestamp_str = "??:??:??"
    
    sender = message.get("sender", "unknown").ljust(20)
    action = message.get("action", "").ljust(15)
    
    # Determinar cor e tipo
    msg_type = message.get("type", "info").lower()
    
    # Formatar conteúdo
    content = message.get("content", "")
    if isinstance(content, dict):
        content = json.dumps(content, indent=2, ensure_ascii=False)
    
    # Linha formatada
    line = f"[{timestamp_str}] {sender} | {action} | {content[:80]}"
    if len(content) > 80:
        line += "..."
    
    return line, msg_type

def fetch_conversations() -> str:
    """Buscar todas as conversas e retornar como texto"""
    try:
        interceptor = get_interceptor()
        conversations_list = interceptor.list_conversations(limit=1000)
        
        output_lines = []
        output_lines.append("=" * 120)
        output_lines.append(f"🔍 INTERCEPTADOR DE CONVERSAS | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append("=" * 120)
        output_lines.append("")
        
        if not conversations_list:
            output_lines.append("⏳ Aguardando conversas... Nenhuma conversa capturada ainda.")
            output_lines.append("")
        else:
            # Agrupar por conversa
            for conv_data in conversations_list:
                conv_id = conv_data.get('id', conv_data.get('conversation_id', 'unknown'))
                output_lines.append(f"📦 CONVERSA: {conv_id}")
                output_lines.append(f"   Status: {conv_data.get('status', 'unknown')}")
                output_lines.append(f"   Fase: {conv_data.get('current_phase', 'unknown')}")
                output_lines.append(f"   Mensagens: {conv_data.get('message_count', len(conv_data.get('messages', [])))}")
                output_lines.append(f"   Criada: {conv_data.get('created_at', 'unknown')}")
                output_lines.append("-" * 120)
                
                # Mensagens
                messages = conv_data.get("messages", [])
                if messages:
                    for msg in messages[-50:]:  # Últimas 50 mensagens
                        line, msg_type = format_message(msg)
                        output_lines.append(line)
                else:
                    output_lines.append("   (sem mensagens)")
                
                output_lines.append("")
        
        output_lines.append("=" * 120)
        return "\n".join(output_lines)
    
    except Exception as e:
        import traceback
        return f"❌ Erro ao buscar conversas: {str(e)}\n\n{traceback.format_exc()}"

def get_stats() -> Dict[str, Any]:
    """Obter estatísticas das conversas"""
    try:
        interceptor = get_interceptor()
        conversations = interceptor.list_conversations(limit=1000)
        
        total_conversations = len(conversations)
        total_messages = sum(c.get("message_count", len(c.get("messages", []))) for c in conversations)
        
        active_conversations = len([c for c in conversations if c.get("status") == "active"])
        completed_conversations = len([c for c in conversations if c.get("status") == "completed"])
        
        # Agentes únicos
        agents = set()
        for conv in conversations:
            for msg in conv.get("messages", []):
                sender = msg.get("sender", "")
                if sender:
                    agents.add(sender)
        
        return {
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "completed_conversations": completed_conversations,
            "total_messages": total_messages,
            "unique_agents": len(agents),
            "agents": list(agents)
        }
    except Exception as e:
        return {"error": str(e)}

# ========== LAYOUT PRINCIPAL ==========

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.title("💬 Conversas dos Agentes")
    st.markdown("_Interface em tempo real com textbox rolante_")

with col2:
    if st.button("🔄 Atualizar", use_container_width=True):
        st.rerun()

st.divider()

# Painel de Controle
with st.container():
    st.markdown("**⚙️ Controles**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        auto_refresh = st.checkbox("🔄 Auto-refresh", value=True, help="Atualiza automaticamente")
    
    with col2:
        refresh_rate = st.selectbox(
            "Intervalo",
            [1, 2, 3, 5, 10],
            index=0,
            format_func=lambda x: f"{x}s",
            label_visibility="collapsed"
        )
    
    with col3:
        filter_agent = st.selectbox(
            "Filtrar por Agente",
            ["Todos", "PythonAgent", "JavaScriptAgent", "TypeScriptAgent", "GoAgent", "TestAgent", "OperationsAgent", "RequirementsAnalyst"],
            label_visibility="collapsed"
        )
    
    with col4:
        limit_messages = st.number_input(
            "Últimas N mensagens",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            label_visibility="collapsed"
        )

st.divider()

# Estatísticas em tempo real
stats = get_stats()
if "error" not in stats:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📊 Conversas", stats["total_conversations"])
    with col2:
        st.metric("✅ Ativas", stats["active_conversations"])
    with col3:
        st.metric("🏁 Completadas", stats["completed_conversations"])
    with col4:
        st.metric("💬 Mensagens", stats["total_messages"])
    with col5:
        st.metric("🤖 Agentes", stats["unique_agents"])

st.divider()

# Textbox principal com conversas - TEMPO REAL ROLANTE
st.markdown("**📝 Stream de Conversas (Tempo Real)**")

# Container para o textbox com auto-scroll
conversation_text = fetch_conversations()

# CSS e JavaScript para auto-scroll em tempo real
st.markdown("""
<style>
    #realtime-box {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Monaco', monospace;
        font-size: 12px;
        line-height: 1.5;
        height: 500px;
        overflow-y: auto;
        color: #c9d1d9;
        scroll-behavior: smooth;
    }
    
    #realtime-box::-webkit-scrollbar {
        width: 8px;
    }
    
    #realtime-box::-webkit-scrollbar-track {
        background: #21262d;
        border-radius: 4px;
    }
    
    #realtime-box::-webkit-scrollbar-thumb {
        background: #30363d;
        border-radius: 4px;
    }
    
    #realtime-box::-webkit-scrollbar-thumb:hover {
        background: #58a6ff;
    }
    
    .msg-line {
        padding: 2px 0;
        border-bottom: 1px solid #21262d;
    }
    
    .timestamp {
        color: #8b949e;
        font-size: 11px;
    }
    
    .agent-name {
        color: #58a6ff;
        font-weight: bold;
    }
    
    .arrow {
        color: #f0883e;
    }
    
    .target-name {
        color: #a371f7;
    }
    
    .msg-content {
        color: #7ee787;
    }
    
    .conv-header {
        color: #ffa657;
        font-weight: bold;
        margin-top: 10px;
        padding: 5px;
        background: #21262d;
        border-radius: 4px;
    }
    
    .separator {
        color: #30363d;
        text-align: center;
    }
    
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 10px;
        margin-left: 8px;
    }
    
    .status-active {
        background: #238636;
        color: #ffffff;
    }
    
    .status-completed {
        background: #1f6feb;
        color: #ffffff;
    }
    
    .blink {
        animation: blink-animation 1s steps(2, start) infinite;
    }
    
    @keyframes blink-animation {
        to { visibility: hidden; }
    }
    
    .live-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #3fb950;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 1.5s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.2); }
        100% { opacity: 1; transform: scale(1); }
    }
</style>
""", unsafe_allow_html=True)

# Formatar conversas com cores e estilos
def format_html_conversations():
    try:
        interceptor = get_interceptor()
        conversations_list = interceptor.list_conversations(limit=50)
        
        lines = []
        lines.append(f'<div class="separator">{"═" * 80}</div>')
        lines.append(f'<div style="text-align:center; color:#58a6ff; font-weight:bold;"><span class="live-indicator"></span>STREAM AO VIVO | {datetime.now().strftime("%H:%M:%S")}</div>')
        lines.append(f'<div class="separator">{"═" * 80}</div>')
        
        if not conversations_list:
            lines.append('<div style="text-align:center; color:#ffa657; padding:20px;">⏳ Aguardando conversas...</div>')
        else:
            for conv_data in conversations_list[:20]:  # Últimas 20 conversas
                conv_id = conv_data.get('id', conv_data.get('conversation_id', 'unknown'))
                status = conv_data.get('status', 'active')
                status_class = 'status-active' if status == 'active' else 'status-completed'
                msg_count = conv_data.get('message_count', 0)
                
                lines.append(f'<div class="conv-header">📦 {conv_id[:40]}... <span class="status-badge {status_class}">{status}</span> ({msg_count} msgs)</div>')
                
                messages = conv_data.get("messages", [])
                if messages:
                    for msg in messages[-10:]:  # Últimas 10 por conversa
                        ts = msg.get("timestamp", "")[-8:] if msg.get("timestamp") else "??:??:??"
                        sender = msg.get("sender", "unknown")
                        target = msg.get("target", "unknown")
                        content = msg.get("content", "")[:100]
                        
                        lines.append(f'''
                        <div class="msg-line">
                            <span class="timestamp">[{ts}]</span>
                            <span class="agent-name">{sender}</span>
                            <span class="arrow">→</span>
                            <span class="target-name">{target}</span>
                            <span class="msg-content">: {content}</span>
                        </div>
                        ''')
                else:
                    lines.append('<div style="color:#8b949e; padding-left:20px;">(sem mensagens)</div>')
                
                lines.append('<div class="separator">─</div>')
        
        lines.append(f'<div class="separator">{"═" * 80}</div>')
        return "\n".join(lines)
    except Exception as e:
        return f'<div style="color:#f85149;">❌ Erro: {str(e)}</div>'

html_content = format_html_conversations()

st.markdown(f"""
<div id="realtime-box">
{html_content}
</div>

<script>
// Auto-scroll para o final
(function() {{
    var box = document.getElementById('realtime-box');
    if (box) {{
        box.scrollTop = box.scrollHeight;
    }}
}})();
</script>
""", unsafe_allow_html=True)

st.divider()

# Footer com instruções
st.markdown("""
**💡 Dicas:**
- O **auto-refresh** está ativado por padrão - veja as conversas em tempo real!
- Use os **filtros** para focar em agentes específicos
- As **cores** indicam: 🔵 Agente origem | 🟣 Agente destino | 🟢 Conteúdo
- O indicador **verde pulsante** mostra que o stream está ao vivo
""")

# Auto-refresh com intervalo configurável
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()

