"""
Agent Communication Monitor
Painel para visualização em tempo real das conversas entre agents.
Usa o AgentCommunicationBus existente via API.
"""

import streamlit as st
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests

# Configuração da página
st.set_page_config(
    page_title="🤖 Agent Monitor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #0e1117 0%, #1a1f2e 100%);
    }
    
    .message-card {
        background: #1e2130;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid;
        animation: slideIn 0.3s ease-out;
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    .agent-python { border-left-color: #3572A5; }
    .agent-javascript { border-left-color: #f7df1e; }
    .agent-typescript { border-left-color: #3178c6; }
    .agent-go { border-left-color: #00ADD8; }
    .agent-rust { border-left-color: #dea584; }
    .agent-coordinator { border-left-color: #00ff88; }
    .agent-analyst { border-left-color: #ff6b6b; }
    .agent-operations { border-left-color: #ffd93d; }
    .agent-test { border-left-color: #9c27b0; }
    .agent-llm { border-left-color: #00d4ff; }
    .agent-docker { border-left-color: #2496ED; }
    .agent-github { border-left-color: #ffffff; }
    .agent-rag { border-left-color: #ff9800; }
    
    .timestamp {
        color: #666;
        font-size: 0.8em;
    }
    
    .agent-name {
        font-weight: bold;
        font-size: 1.1em;
    }
    
    .message-content {
        margin-top: 10px;
        padding: 10px;
        background: #252836;
        border-radius: 5px;
        font-family: 'Fira Code', monospace;
        white-space: pre-wrap;
        word-wrap: break-word;
        max-height: 200px;
        overflow-y: auto;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #1e2130 0%, #252836 100%);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        border: 1px solid #333;
    }
    
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
        background: linear-gradient(90deg, #00ff88, #00d4ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .status-online { color: #00ff88; }
    .status-offline { color: #ff4444; }
    .status-busy { color: #ffd93d; }
    
    .live-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        background: #00ff88;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 1.5s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); }
        50% { opacity: 0.8; box-shadow: 0 0 0 10px rgba(0, 255, 136, 0); }
    }
    
    .type-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75em;
        font-weight: bold;
        margin-left: 10px;
    }
    
    .type-request { background: #2196F3; color: white; }
    .type-response { background: #4CAF50; color: white; }
    .type-llm_call { background: #9C27B0; color: white; }
    .type-llm_response { background: #673AB7; color: white; }
    .type-code_gen { background: #FF5722; color: white; }
    .type-execution { background: #795548; color: white; }
    .type-error { background: #F44336; color: white; }
    .type-docker { background: #2496ED; color: white; }
    .type-github { background: #333; color: white; }
    .type-rag { background: #FF9800; color: black; }
    .type-coordinator { background: #00ff88; color: black; }
    .type-analysis { background: #E91E63; color: white; }
    .type-task_start { background: #00BCD4; color: white; }
    .type-task_end { background: #009688; color: white; }
</style>
""", unsafe_allow_html=True)


# Configurações padrão
DEFAULT_API_URL = "http://192.168.15.2:8503"

# Session state
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True
if 'refresh_rate' not in st.session_state:
    st.session_state.refresh_rate = 2
if 'api_url' not in st.session_state:
    st.session_state.api_url = DEFAULT_API_URL


def get_agent_color(agent_name: str) -> str:
    """Retorna a classe CSS para o agent."""
    agent_lower = agent_name.lower()
    if "python" in agent_lower:
        return "agent-python"
    elif "javascript" in agent_lower or "js" in agent_lower:
        return "agent-javascript"
    elif "typescript" in agent_lower or "ts" in agent_lower:
        return "agent-typescript"
    elif "go" in agent_lower or "golang" in agent_lower:
        return "agent-go"
    elif "rust" in agent_lower:
        return "agent-rust"
    elif "coordinator" in agent_lower:
        return "agent-coordinator"
    elif "analyst" in agent_lower or "requisitos" in agent_lower:
        return "agent-analyst"
    elif "operations" in agent_lower or "ops" in agent_lower:
        return "agent-operations"
    elif "test" in agent_lower:
        return "agent-test"
    elif "llm" in agent_lower or "ollama" in agent_lower:
        return "agent-llm"
    elif "docker" in agent_lower:
        return "agent-docker"
    elif "github" in agent_lower:
        return "agent-github"
    elif "rag" in agent_lower:
        return "agent-rag"
    return "agent-coordinator"


def get_message_icon(msg_type: str) -> str:
    """Retorna emoji para tipo de mensagem."""
    icons = {
        "request": "📤",
        "response": "📥",
        "task_start": "▶️",
        "task_end": "⏹️",
        "llm_call": "🧠",
        "llm_response": "💭",
        "code_gen": "💻",
        "test_gen": "🧪",
        "execution": "⚡",
        "error": "❌",
        "docker": "🐳",
        "rag": "📚",
        "github": "🐙",
        "coordinator": "🎯",
        "analysis": "🔍"
    }
    return icons.get(msg_type, "💬")


def fetch_messages(api_url: str, limit: int = 100, msg_type: str = None) -> List[Dict]:
    """Busca mensagens da API."""
    try:
        params = {"limit": limit}
        if msg_type and msg_type != "all":
            params["message_type"] = msg_type
            
        response = requests.get(
            f"{api_url}/communication/messages",
            params=params,
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("messages", [])
    except Exception as e:
        pass
    return []


def fetch_stats(api_url: str) -> Dict:
    """Busca estatísticas da API."""
    try:
        response = requests.get(f"{api_url}/communication/stats", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"total_messages": 0, "by_type": {}, "by_agent": {}}


def fetch_system_status(api_url: str) -> Dict:
    """Busca status do sistema."""
    try:
        response = requests.get(f"{api_url}/status", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {}


def send_test_message(api_url: str, message: str) -> bool:
    """Envia mensagem de teste."""
    try:
        response = requests.post(
            f"{api_url}/communication/test",
            params={"message": message},
            timeout=5
        )
        return response.status_code == 200
    except:
        return False


def render_message(msg: Dict):
    """Renderiza uma mensagem no formato de card."""
    source = msg.get("source", "Unknown")
    target = msg.get("target", "Unknown")
    msg_type = msg.get("type", "request")
    content = msg.get("content", "")
    timestamp = msg.get("timestamp", "")
    
    agent_class = get_agent_color(source)
    icon = get_message_icon(msg_type)
    
    # Formatar timestamp
    try:
        ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        ts_str = ts.strftime('%H:%M:%S.%f')[:-3]
    except:
        ts_str = timestamp[:19] if timestamp else ""
    
    # Truncar conteúdo se muito grande
    display_content = content[:800] + "..." if len(content) > 800 else content
    # Escapar HTML
    display_content = display_content.replace("<", "&lt;").replace(">", "&gt;")
    
    st.markdown(f"""
    <div class="message-card {agent_class}">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <span class="agent-name">{icon} {source} → {target}</span>
            <span>
                <span class="type-badge type-{msg_type}">{msg_type.upper()}</span>
                <span class="timestamp">{ts_str}</span>
            </span>
        </div>
        <div class="message-content">{display_content}</div>
    </div>
    """, unsafe_allow_html=True)


# ============== SIDEBAR ==============
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    
    # URL da API
    st.session_state.api_url = st.text_input("API URL", value=st.session_state.api_url)
    
    st.markdown("---")
    
    # Auto-refresh
    st.session_state.auto_refresh = st.toggle(
        "🔄 Auto-refresh",
        value=st.session_state.auto_refresh
    )
    
    if st.session_state.auto_refresh:
        st.session_state.refresh_rate = st.slider(
            "Taxa de atualização (segundos)",
            min_value=1,
            max_value=10,
            value=st.session_state.refresh_rate
        )
    
    st.markdown("---")
    
    # Filtros
    st.markdown("### 🔍 Filtros")
    
    type_options = ["all", "request", "response", "task_start", "task_end",
                   "llm_call", "llm_response", "code_gen", "test_gen",
                   "execution", "error", "docker", "github", 
                   "rag", "coordinator", "analysis"]
    
    type_filter = st.selectbox(
        "Tipo de Mensagem",
        type_options,
        format_func=lambda x: "Todos" if x == "all" else x.upper()
    )
    
    msg_limit = st.slider("Número de mensagens", 10, 200, 50)
    
    st.markdown("---")
    
    # Ações
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🗑️ Limpar", use_container_width=True):
            try:
                requests.post(f"{st.session_state.api_url}/communication/clear", timeout=5)
                st.success("Logs limpos!")
            except Exception as e:
                st.error(f"Erro: {e}")
    
    st.markdown("---")
    
    # Enviar mensagem de teste
    st.markdown("### 📤 Teste")
    test_msg = st.text_input("Mensagem de teste")
    if st.button("Enviar", use_container_width=True):
        if test_msg:
            if send_test_message(st.session_state.api_url, test_msg):
                st.success("Enviado!")
            else:
                st.error("Falha ao enviar")
    
    st.markdown("---")
    
    # Exportar
    if st.button("📥 Exportar JSON", use_container_width=True):
        messages = fetch_messages(st.session_state.api_url, limit=500)
        if messages:
            st.download_button(
                "Download",
                data=json.dumps(messages, indent=2, default=str),
                file_name=f"agent_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        else:
            st.warning("Nenhuma mensagem para exportar")


# ============== MAIN CONTENT ==============

# Header
st.markdown("""
<div style="text-align: center; padding: 20px 0;">
    <h1 style="background: linear-gradient(90deg, #00ff88, #00d4ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🤖 Agent Communication Monitor
    </h1>
    <p style="color: #888;">Visualização em tempo real das conversas entre agents</p>
</div>
""", unsafe_allow_html=True)

# Status indicator
if st.session_state.auto_refresh:
    st.markdown(f"""
    <div style="text-align: center; padding: 10px;">
        <span class="live-indicator"></span>
        <span style="color: #00ff88; font-weight: bold;">LIVE</span>
        <span style="color: #666;"> - Atualizando a cada {st.session_state.refresh_rate}s</span>
    </div>
    """, unsafe_allow_html=True)

# Buscar dados
api_url = st.session_state.api_url
stats = fetch_stats(api_url)
system_status = fetch_system_status(api_url)
messages = fetch_messages(api_url, limit=msg_limit, msg_type=type_filter if type_filter != "all" else None)

# Métricas
st.markdown("### 📊 Métricas em Tempo Real")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total = stats.get("total_messages", len(messages))
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{total}</div>
        <div style="color: #888;">Total de Mensagens</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    active_agents = len(stats.get("by_agent", {}))
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{active_agents}</div>
        <div style="color: #888;">Agents Ativos</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    llm_calls = stats.get("by_type", {}).get("llm_call", 0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{llm_calls}</div>
        <div style="color: #888;">Chamadas LLM</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    errors = stats.get("by_type", {}).get("error", 0)
    error_color = "#ff4444" if errors > 0 else "#00ff88"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="background: {error_color}; -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{errors}</div>
        <div style="color: #888;">Erros</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Layout principal
left_col, right_col = st.columns([2, 1])

# Feed de mensagens
with left_col:
    st.markdown("### 💬 Feed de Comunicações")
    
    if messages:
        for msg in messages:
            render_message(msg)
    else:
        st.info("📭 Nenhuma mensagem encontrada. Aguardando comunicações entre agents...")
        st.markdown("""
        **Dicas:**
        - Verifique se a API está rodando em `{}`
        - Use o Telegram ou Open WebUI para acionar os agents
        - Envie uma mensagem de teste no sidebar
        """.format(api_url))

# Status dos Agents e tipos
with right_col:
    st.markdown("### 🤖 Agents")
    
    agent_stats = stats.get("by_agent", {})
    if agent_stats:
        for agent_name, count in sorted(agent_stats.items(), key=lambda x: -x[1]):
            agent_class = get_agent_color(agent_name)
            st.markdown(f"""
            <div style="background: #1e2130; border-radius: 10px; padding: 12px; margin: 8px 0; border-left: 4px solid;" class="{agent_class}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: bold;">{agent_name}</span>
                    <span style="color: #00ff88;">{count} msgs</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhum agent ativo")
    
    st.markdown("### 📈 Por Tipo")
    
    type_stats = stats.get("by_type", {})
    if type_stats:
        for msg_type, count in sorted(type_stats.items(), key=lambda x: -x[1]):
            icon = get_message_icon(msg_type)
            st.markdown(f"""
            <div style="background: #252836; padding: 8px 12px; margin: 4px 0; border-radius: 5px; display: flex; justify-content: space-between;">
                <span>{icon} {msg_type}</span>
                <span style="color: #00d4ff;">{count}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhuma atividade")
    
    st.markdown("### 🖥️ Sistema")
    
    docker_ok = system_status.get("docker_available", False)
    github_ok = system_status.get("github_configured", False)
    rag_ok = system_status.get("rag_available", False)
    
    st.markdown(f"""
    <div style="background: #1e2130; padding: 15px; border-radius: 10px; margin-top: 10px;">
        <div style="margin: 5px 0;">🐳 Docker: <span class="{'status-online' if docker_ok else 'status-offline'}">{'✅ OK' if docker_ok else '❌ Offline'}</span></div>
        <div style="margin: 5px 0;">🐙 GitHub: <span class="{'status-online' if github_ok else 'status-offline'}">{'✅ OK' if github_ok else '❌ Não config'}</span></div>
        <div style="margin: 5px 0;">📚 RAG: <span class="{'status-online' if rag_ok else 'status-offline'}">{'✅ OK' if rag_ok else '❌ Offline'}</span></div>
    </div>
    """, unsafe_allow_html=True)


# Auto-refresh
if st.session_state.auto_refresh:
    time.sleep(st.session_state.refresh_rate)
    st.rerun()

# Footer
st.markdown("---")
st.markdown(f"""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>Agent Communication Monitor v1.0 | Eddie Auto-Dev</p>
    <p style="font-size: 0.8em;">
        📡 Conectado a: {api_url}
    </p>
</div>
""", unsafe_allow_html=True)
