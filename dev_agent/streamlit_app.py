"""Eddie Coordinator Dashboard — minimal Streamlit UI."""
from __future__ import annotations

import os
import sys
import time

import streamlit as st

st.set_page_config(
    page_title="Eddie Coordinator",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Eddie Coordinator Dashboard")

# Sidebar — connection info
with st.sidebar:
    st.header("Configuração")
    ollama_host = st.text_input("Ollama Host", value=os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434"))
    ollama_model = st.text_input("Modelo", value=os.getenv("OLLAMA_MODEL", "phi4-mini"))
    rag_url = st.text_input("RAG API URL", value=os.getenv("RAG_API_URL", ""))

# Main area
tab1, tab2, tab3 = st.tabs(["Nova Tarefa", "Status do Agente", "Bus de Mensagens"])

with tab1:
    st.subheader("Executar Tarefa")
    description = st.text_area("Descrição da tarefa", height=150, placeholder="Descreva o que precisa ser desenvolvido...")
    language = st.selectbox("Linguagem", ["python", "javascript", "sql", "bash"])

    if st.button("▶ Executar", type="primary"):
        if not description.strip():
            st.error("Informe uma descrição para a tarefa.")
        else:
            with st.spinner("Processando..."):
                try:
                    sys.path.insert(0, "/home/homelab/eddie-auto-dev")
                    os.environ.setdefault("OLLAMA_HOST", ollama_host)
                    os.environ.setdefault("OLLAMA_MODEL", ollama_model)
                    from dev_agent.agent import DevAgent
                    from dev_agent.coordinator import CoordinatorAgent
                    agent = DevAgent(llm_url=ollama_host, model=ollama_model)
                    coordinator = CoordinatorAgent(dev_agent=agent, rag_api_url=rag_url)
                    result = coordinator.decide_and_execute(description, language)
                    if result.get("success"):
                        st.success("✅ Tarefa concluída!")
                        st.code(result.get("code", ""), language=language)
                    else:
                        st.warning("⚠️ Tarefa não concluída automaticamente.")
                        st.json(result)
                except Exception as e:
                    st.error(f"Erro: {e}")

with tab2:
    st.subheader("Status do CoordinatorAgent")
    if st.button("🔄 Verificar"):
        try:
            import subprocess
            result = subprocess.run(
                ["systemctl", "is-active", "coordinator-agent"],
                capture_output=True, text=True,
            )
            state = result.stdout.strip()
            if state == "active":
                st.success(f"coordinator-agent: {state}")
            else:
                st.error(f"coordinator-agent: {state}")

            result = subprocess.run(
                ["systemctl", "is-active", "diretor"],
                capture_output=True, text=True,
            )
            state = result.stdout.strip()
            if state == "active":
                st.success(f"diretor: {state}")
            else:
                st.error(f"diretor: {state}")
        except Exception as e:
            st.error(f"Erro ao verificar status: {e}")

with tab3:
    st.subheader("Mensagens Recentes no Bus")
    if st.button("🔄 Atualizar"):
        try:
            sys.path.insert(0, "/home/homelab/eddie-auto-dev")
            from specialized_agents.agent_communication_bus import AgentCommunicationBus
            bus = AgentCommunicationBus()
            messages = bus.get_messages(limit=20)
            if messages:
                for msg in reversed(messages):
                    with st.expander(f"[{msg.message_type.value}] {msg.source} → {msg.target}  ({msg.timestamp.strftime('%H:%M:%S')})"):
                        st.text(msg.content[:500] + ("..." if len(msg.content) > 500 else ""))
            else:
                st.info("Nenhuma mensagem no buffer.")
        except Exception as e:
            st.error(f"Erro ao ler bus: {e}")
