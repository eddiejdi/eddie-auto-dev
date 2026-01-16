#!/usr/bin/env python3
"""
Interface Simples para Visualizar Conversas dos Agentes
Sem auto-refresh que pisca - atualização manual com scroll suave
"""
import streamlit as st
import json
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
import sys
import os

# Adicionar path do projeto raiz
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)
os.chdir(project_root)

# Import usando path absoluto
from specialized_agents.agent_interceptor import get_agent_interceptor

# Configuração da página
st.set_page_config(
    page_title="💬 Conversas dos Agentes",
    page_icon="💬",
    layout="wide"
)

# CSS Global - Tema escuro com scroll suave
st.markdown("""
<style>
    /* Reset e base */
    .stApp {
        background-color: #0d1117;
    }
    
    /* Container principal do stream */
    #stream-container {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 0;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 13px;
        line-height: 1.6;
        height: 550px;
        overflow-y: auto;
        color: #c9d1d9;
        scroll-behavior: smooth;
        -webkit-overflow-scrolling: touch;
    }
    
    /* Scrollbar customizada */
    #stream-container::-webkit-scrollbar {
        width: 10px;
    }
    
    #stream-container::-webkit-scrollbar-track {
        background: #21262d;
        border-radius: 5px;
    }
    
    #stream-container::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #30363d 0%, #484f58 100%);
        border-radius: 5px;
        border: 2px solid #21262d;
    }
    
    #stream-container::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #58a6ff 0%, #1f6feb 100%);
    }
    
    /* Header fixo */
    .stream-header {
        position: sticky;
        top: 0;
        background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
        padding: 12px 16px;
        border-bottom: 1px solid #30363d;
        z-index: 100;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }
    
    .live-dot {
        width: 10px;
        height: 10px;
        background: #3fb950;
        border-radius: 50%;
        box-shadow: 0 0 10px #3fb950;
        animation: pulse-glow 2s ease-in-out infinite;
    }
    
    @keyframes pulse-glow {
        0%, 100% { 
            opacity: 1; 
            box-shadow: 0 0 10px #3fb950;
        }
        50% { 
            opacity: 0.7; 
            box-shadow: 0 0 20px #3fb950, 0 0 30px #3fb950;
        }
    }
    
    .stream-title {
        color: #58a6ff;
        font-weight: 600;
        font-size: 14px;
        letter-spacing: 1px;
    }
    
    .stream-time {
        color: #8b949e;
        font-size: 12px;
    }
    
    /* Conteúdo das mensagens */
    .stream-content {
        padding: 16px;
    }
    
    /* Card de conversa */
    .conv-card {
        background: rgba(33, 38, 45, 0.5);
        border: 1px solid #30363d;
        border-left: 4px solid #f0883e;
        border-radius: 8px;
        margin-bottom: 16px;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .conv-card:hover {
        border-color: #58a6ff;
        box-shadow: 0 4px 12px rgba(88, 166, 255, 0.15);
    }
    
    .conv-header {
        background: #21262d;
        padding: 10px 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
    }
    
    .conv-id {
        color: #ffa657;
        font-weight: 600;
        font-size: 12px;
    }
    
    .conv-meta {
        display: flex;
        gap: 12px;
        align-items: center;
    }
    
    .badge {
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .badge-active {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: #ffffff;
    }
    
    .badge-completed {
        background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%);
        color: #ffffff;
    }
    
    .msg-count {
        color: #8b949e;
        font-size: 11px;
    }
    
    /* Mensagens */
    .conv-messages {
        padding: 12px 14px;
    }
    
    .msg-row {
        padding: 8px 0;
        border-bottom: 1px solid rgba(48, 54, 61, 0.5);
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: baseline;
        transition: background 0.2s ease;
    }
    
    .msg-row:last-child {
        border-bottom: none;
    }
    
    .msg-row:hover {
        background: rgba(88, 166, 255, 0.05);
        border-radius: 4px;
    }
    
    .msg-time {
        color: #6e7681;
        font-size: 11px;
        min-width: 70px;
    }
    
    .msg-from {
        color: #58a6ff;
        font-weight: 600;
    }
    
    .msg-arrow {
        color: #f0883e;
    }
    
    .msg-to {
        color: #a371f7;
        font-weight: 600;
    }
    
    .msg-text {
        color: #7ee787;
        flex: 1;
        word-break: break-word;
    }
    
    /* Estado vazio */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #8b949e;
    }
    
    .empty-icon {
        font-size: 48px;
        margin-bottom: 16px;
    }
    
    /* Footer */
    .stream-footer {
        padding: 12px 16px;
        background: #161b22;
        border-top: 1px solid #30363d;
        text-align: center;
        color: #6e7681;
        font-size: 11px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_interceptor():
    """Obter instância do interceptor"""
    return get_agent_interceptor()


def get_stats() -> Dict[str, Any]:
    """Obter estatísticas das conversas"""
    try:
        interceptor = get_interceptor()
        conversations = interceptor.list_conversations(limit=1000)
        
        total_conversations = len(conversations)
        total_messages = sum(c.get("message_count", len(c.get("messages", []))) for c in conversations)
        
        active_conversations = len([c for c in conversations if c.get("status") == "active"])
        completed_conversations = len([c for c in conversations if c.get("status") == "completed"])
        
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


def render_conversations_html(filter_agent: str = "Todos", limit: int = 20) -> str:
    """Renderizar conversas em HTML formatado"""
    try:
        interceptor = get_interceptor()
        conversations_list = interceptor.list_conversations(limit=limit)
        
        # Filtrar por agente se necessário
        if filter_agent != "Todos":
            filtered = []
            for conv in conversations_list:
                for msg in conv.get("messages", []):
                    if filter_agent in msg.get("sender", "") or filter_agent in msg.get("target", ""):
                        filtered.append(conv)
                        break
            conversations_list = filtered
        
        html_parts = []
        
        # Header fixo
        html_parts.append(f'''
        <div class="stream-header">
            <div class="live-dot"></div>
            <span class="stream-title">STREAM DE CONVERSAS</span>
            <span class="stream-time">Atualizado: {datetime.now().strftime("%H:%M:%S")}</span>
        </div>
        ''')
        
        html_parts.append('<div class="stream-content">')
        
        if not conversations_list:
            html_parts.append('''
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <div>Nenhuma conversa encontrada</div>
                <div style="margin-top: 8px; font-size: 12px;">As conversas aparecerão aqui em tempo real</div>
            </div>
            ''')
        else:
            for conv in conversations_list:
                conv_id = conv.get('id', conv.get('conversation_id', 'unknown'))
                status = conv.get('status', 'active')
                badge_class = 'badge-active' if status == 'active' else 'badge-completed'
                msg_count = conv.get('message_count', 0)
                messages = conv.get("messages", [])
                
                html_parts.append(f'''
                <div class="conv-card">
                    <div class="conv-header">
                        <span class="conv-id">📦 {conv_id[:35]}...</span>
                        <div class="conv-meta">
                            <span class="badge {badge_class}">{status}</span>
                            <span class="msg-count">💬 {msg_count} msgs</span>
                        </div>
                    </div>
                    <div class="conv-messages">
                ''')
                
                if messages:
                    for msg in messages[-8:]:  # Últimas 8 mensagens por conversa
                        ts = msg.get("timestamp", "")
                        if ts:
                            ts = ts[-8:] if len(ts) > 8 else ts
                        else:
                            ts = "--:--:--"
                        
                        sender = msg.get("sender", "?")
                        target = msg.get("target", "?")
                        content = msg.get("content", "")[:120]
                        if len(msg.get("content", "")) > 120:
                            content += "..."
                        
                        html_parts.append(f'''
                        <div class="msg-row">
                            <span class="msg-time">[{ts}]</span>
                            <span class="msg-from">{sender}</span>
                            <span class="msg-arrow">→</span>
                            <span class="msg-to">{target}</span>
                            <span class="msg-text">{content}</span>
                        </div>
                        ''')
                else:
                    html_parts.append('<div style="color: #6e7681; padding: 8px;">(sem mensagens)</div>')
                
                html_parts.append('</div></div>')
        
        html_parts.append('</div>')
        
        # Footer
        html_parts.append(f'''
        <div class="stream-footer">
            Mostrando {len(conversations_list)} conversas • Clique em "Atualizar" para ver novas mensagens
        </div>
        ''')
        
        return "\n".join(html_parts)
    
    except Exception as e:
        return f'<div class="empty-state"><div class="empty-icon">❌</div>Erro: {str(e)}</div>'


# ========== LAYOUT PRINCIPAL ==========

# Header
st.title("💬 Conversas dos Agentes")
st.caption("Interface de monitoramento em tempo real")

# Botão de atualização proeminente
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    if st.button("🔄 Atualizar Conversas", use_container_width=True, type="primary"):
        st.cache_resource.clear()
        st.rerun()

st.divider()

# Controles em uma linha
col1, col2 = st.columns(2)

with col1:
    filter_agent = st.selectbox(
        "🔍 Filtrar por Agente",
        [
            "Todos",
            "PythonAgent",
            "JavaScriptAgent", 
            "TypeScriptAgent",
            "GoAgent",
            "RustAgent",
            "JavaAgent",
            "CSharpAgent",
            "PHPAgent",
            "TestAgent",
            "OperationsAgent",
            "RequirementsAnalyst",
            "GitHubAgent",
            "AgentManager",
            "Coordinator",
            "AutoScaler"
        ]
    )

with col2:
    limit_convs = st.slider("📊 Número de conversas", 5, 50, 15)

st.divider()

# Estatísticas compactas
stats = get_stats()
if "error" not in stats:
    cols = st.columns(5)
    metrics = [
        ("📊 Total", stats["total_conversations"]),
        ("✅ Ativas", stats["active_conversations"]),
        ("🏁 Completas", stats["completed_conversations"]),
        ("💬 Mensagens", stats["total_messages"]),
        ("🤖 Agentes", stats["unique_agents"])
    ]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)

st.divider()

# Container principal com as conversas
html_content = render_conversations_html(filter_agent, limit_convs)

st.markdown(f'''
<div id="stream-container">
{html_content}
</div>

<script>
// Scroll suave para o final
(function() {{
    setTimeout(function() {{
        var container = document.getElementById('stream-container');
        if (container) {{
            container.scrollTo({{
                top: container.scrollHeight,
                behavior: 'smooth'
            }});
        }}
    }}, 100);
}})();
</script>
''', unsafe_allow_html=True)

st.divider()

# Dicas
with st.expander("💡 Como usar", expanded=False):
    st.markdown("""
    - **Atualizar**: Clique no botão azul para ver as mensagens mais recentes
    - **Filtrar**: Use o dropdown para ver apenas um agente específico
    - **Scroll**: Role dentro do container para ver mensagens anteriores
    - **Cores**: 
        - 🔵 Azul = Agente de origem
        - 🟣 Roxo = Agente de destino  
        - 🟢 Verde = Conteúdo da mensagem
    """)

