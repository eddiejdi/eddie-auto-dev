"""
Interface Streamlit para o Dev Agent
"""
import streamlit as st
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dev_agent.agent import DevAgent, ProjectSpec


def get_agent():
    if "agent" not in st.session_state:
        st.session_state.agent = DevAgent()
    return st.session_state.agent


def main():
    st.set_page_config(page_title="Dev Agent", page_icon="🤖", layout="wide")
    st.title("🤖 Dev Agent - Agente de Desenvolvimento Autonomo")
    
    agent = get_agent()
    
    with st.sidebar:
        st.header("⚙️ Status do Sistema")
        if st.button("Verificar Saude"):
            with st.spinner("Verificando..."):
                health = asyncio.run(agent.check_health())
                if health["llm_connected"]:
                    st.success(f"LLM: Conectado ({health['current_model']})")
                else:
                    st.error("LLM: Desconectado")
                if health["docker_available"]:
                    st.success("Docker: Disponivel")
                else:
                    st.error("Docker: Indisponivel")
        
        st.divider()
        st.header("🛠️ Tecnologias")
        techs = agent.get_supported_technologies()
        st.write(", ".join(techs))
    
    tab1, tab2, tab3 = st.tabs(["🚀 Desenvolvimento", "⚡ Execucao Rapida", "💬 Chat"])
    
    with tab1:
        st.header("Criar Codigo Automaticamente")
        description = st.text_area("Descreva o que voce quer criar:", height=100, placeholder="Ex: Uma funcao que calcula fibonacci")
        language = st.selectbox("Linguagem:", ["python", "javascript"])
        
        if st.button("🚀 Desenvolver", type="primary"):
            if description:
                with st.spinner("Gerando e testando codigo..."):
                    result = asyncio.run(agent.develop(description, language))
                    if result["success"]:
                        st.success(f"Codigo criado em {result['iterations']} iteracoes!")
                        st.code(result["code"], language=language)
                    else:
                        st.error("Falha ao criar codigo")
                        for err in result["errors"]:
                            st.warning(err)
    
    with tab2:
        st.header("Executar Codigo")
        code = st.text_area("Cole seu codigo:", height=200, key="quick_code")
        lang = st.selectbox("Linguagem:", ["python", "javascript"], key="quick_lang")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ Executar"):
                if code:
                    with st.spinner("Executando..."):
                        result = asyncio.run(agent.quick_run(code, lang))
                        if result["success"]:
                            st.success("Executado com sucesso!")
                            st.code(result["output"])
                        else:
                            st.error("Erro na execucao")
                            st.code(result["errors"])
        
        with col2:
            if st.button("🔧 Auto-corrigir"):
                if code:
                    with st.spinner("Corrigindo..."):
                        result = asyncio.run(agent.fix_code(code, lang))
                        if result["success"]:
                            st.success(f"Corrigido em {result['iterations']} iteracoes!")
                            st.code(result["fixed_code"], language=lang)
                        else:
                            st.error("Nao foi possivel corrigir")
    
    with tab3:
        st.header("Chat com o Agente")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        if prompt := st.chat_input("Digite sua mensagem..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    response = asyncio.run(agent.chat(prompt))
                    st.write(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
