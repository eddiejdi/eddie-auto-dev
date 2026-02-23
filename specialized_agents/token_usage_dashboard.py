"""
Token Usage Dashboard — Streamlit
Visualiza rastreamento de tokens do bus em tempo real
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json

# Configuração da página
st.set_page_config(
    page_title="Token Usage Dashboard",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo
st.markdown("""
<style>
.metric-card {
    background-color: #f0f2f6;
    border-radius: 0.5rem;
    padding: 1.5rem;
    margin: 0.5rem 0;
}
.high-value {
    color: #d32f2f;
    font-weight: bold;
}
.low-value {
    color: #388e3c;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# Sidebar — Configuração
st.sidebar.title("⚙️ Configuração")
api_url = st.sidebar.text_input(
    "URL da API",
    value="http://localhost:8503",
    help="URL base da API especializada de agentes"
)
refresh_interval = st.sidebar.slider(
    "Atualizar a cada (s)",
    min_value=5,
    max_value=60,
    value=10
)

# Função para buscar dados
@st.cache_data(ttl=5)
def fetch_token_stats():
    try:
        resp = requests.get(f"{api_url}/communication/token-stats", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            return None
    except Exception as e:
        st.warning(f"Erro ao conectar à API: {e}")
        return None

@st.cache_data(ttl=5)
def fetch_communication_stats():
    try:
        resp = requests.get(f"{api_url}/communication/stats", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            return None
    except Exception as e:
        return None

# Main dashboard
st.title("🎫 Token Usage Dashboard")
st.markdown("Rastreamento centralizado de consumo de tokens por modelo e agente")

# Refresh automático
st.markdown(f"*Atualizado a cada {refresh_interval} segundos*")
import time
placeholder = st.empty()

# Fetch data
token_stats = fetch_token_stats()
comm_stats = fetch_communication_stats()

if token_stats:
    # ===== CARDS PRINCIPAIS =====
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total de Tokens",
            f"{token_stats.get('total_tokens', 0):,}",
            delta=f"Avg: {token_stats.get('avg_tokens_per_call', 0):.0f}/call"
        )
    
    with col2:
        st.metric(
            "Tokens de Prompt",
            f"{token_stats.get('total_prompt_tokens', 0):,}",
            delta=f"{(token_stats.get('total_prompt_tokens', 0) / max(token_stats.get('total_tokens', 1), 1) * 100):.1f}%"
        )
    
    with col3:
        st.metric(
            "Tokens de Completion",
            f"{token_stats.get('total_completion_tokens', 0):,}",
            delta=f"{(token_stats.get('total_completion_tokens', 0) / max(token_stats.get('total_tokens', 1), 1) * 100):.1f}%"
        )
    
    with col4:
        st.metric(
            "Total de Chamadas",
            f"{token_stats.get('total_calls', 0):,}",
            delta="requests"
        )
    
    st.divider()
    
    # ===== ABAS =====
    tab1, tab2, tab3 = st.tabs(["📊 Por Modelo", "👤 Por Agente", "📈 Detalhes"])
    
    with tab1:
        st.subheader("Uso de Tokens por Modelo")
        
        if token_stats.get("by_model"):
            models_data = []
            for model, stats in token_stats["by_model"].items():
                models_data.append({
                    "Modelo": model,
                    "Prompt": stats["prompt_tokens"],
                    "Completion": stats["completion_tokens"],
                    "Total": stats["total_tokens"],
                    "Chamadas": stats["calls"]
                })
            
            df_models = pd.DataFrame(models_data)
            
            # Tabela
            st.dataframe(
                df_models.sort_values("Total", ascending=False),
                use_container_width=True,
                hide_index=True
            )
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                fig_tokens = px.pie(
                    df_models,
                    values="Total",
                    names="Modelo",
                    title="Distribuição de Tokens por Modelo"
                )
                st.plotly_chart(fig_tokens, use_container_width=True)
            
            with col2:
                fig_calls = px.bar(
                    df_models.sort_values("Chamadas", ascending=False),
                    x="Modelo",
                    y="Chamadas",
                    title="Número de Chamadas por Modelo",
                    color="Chamadas"
                )
                st.plotly_chart(fig_calls, use_container_width=True)
        else:
            st.info("Nenhum dado de modelo disponível")
    
    with tab2:
        st.subheader("Uso de Tokens por Agente")
        
        if token_stats.get("by_source"):
            source_data = []
            for source, stats in token_stats["by_source"].items():
                source_data.append({
                    "Agente": source,
                    "Prompt": stats["prompt_tokens"],
                    "Completion": stats["completion_tokens"],
                    "Total": stats["total_tokens"],
                    "Chamadas": stats["calls"],
                    "Avg/Call": stats["total_tokens"] / max(stats["calls"], 1)
                })
            
            df_sources = pd.DataFrame(source_data)
            
            # Tabela
            st.dataframe(
                df_sources.sort_values("Total", ascending=False),
                use_container_width=True,
                hide_index=True
            )
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                fig_source_tokens = px.bar(
                    df_sources.sort_values("Total", ascending=False),
                    x="Agente",
                    y="Total",
                    title="Total de Tokens por Agente",
                    color="Total"
                )
                st.plotly_chart(fig_source_tokens, use_container_width=True)
            
            with col2:
                fig_source_calls = px.bar(
                    df_sources.sort_values("Chamadas", ascending=False),
                    x="Agente",
                    y="Chamadas",
                    title="Chamadas por Agente",
                    color="Chamadas"
                )
                st.plotly_chart(fig_source_calls, use_container_width=True)
        else:
            st.info("Nenhum dado de agente disponível")
    
    with tab3:
        st.subheader("Detalhes Completos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Estatísticas Gerais**")
            st.json({
                "total_tokens": token_stats.get("total_tokens"),
                "total_prompt_tokens": token_stats.get("total_prompt_tokens"),
                "total_completion_tokens": token_stats.get("total_completion_tokens"),
                "total_calls": token_stats.get("total_calls"),
                "avg_tokens_per_call": token_stats.get("avg_tokens_per_call"),
                "start_time": token_stats.get("start_time")
            })
        
        with col2:
            if comm_stats:
                st.write("**Comunicação**")
                st.json({
                    "total_messages": comm_stats.get("total_messages"),
                    "buffer_size": comm_stats.get("buffer_size"),
                    "messages_per_minute": f"{comm_stats.get('messages_per_minute', 0):.2f}",
                    "uptime_seconds": f"{comm_stats.get('uptime_seconds', 0):.0f}s"
                })
        
        st.write("**Modelos Rastreados**")
        if token_stats.get("by_model"):
            st.json(token_stats["by_model"])
        
        st.write("**Agentes Rastreados**")
        if token_stats.get("by_source"):
            st.json(token_stats["by_source"])

else:
    st.error(
        f"❌ Não consegui conectar à API em {api_url}\n\n"
        "Certifique-se de que a API está rodando em porta 8503"
    )
    st.code(
        "# Para iniciar a API:\n"
        "source .venv/bin/activate\n"
        "uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503",
        language="bash"
    )

# Footer
st.divider()
st.caption(
    f"🎫 Token Usage Dashboard | "
    f"Última atualização: {datetime.now().strftime('%H:%M:%S')} | "
    f"API: {api_url}"
)
