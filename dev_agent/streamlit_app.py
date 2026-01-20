"""
Interface Streamlit para o Dev Agent - Dashboard de Desenvolvimento
"""
import streamlit as st
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dev_agent.agent import DevAgent, ProjectSpec, TaskStatus
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    IMPORT_ERROR = str(e)


def get_agent():
    if "agent" not in st.session_state:
        st.session_state.agent = DevAgent()
    return st.session_state.agent


def main():
    st.set_page_config(page_title="🤖 Dev Agent", page_icon="🤖", layout="wide")
    
    if not IMPORT_SUCCESS:
        st.error(f"❌ Erro ao carregar módulos: {IMPORT_ERROR}")
        st.info("Verifique se os arquivos em dev_agent/ estão intactos")
        return
    
    st.title("🤖 Dev Agent - Agente de Desenvolvimento Autônomo")
    
    agent = get_agent()
    
    with st.sidebar:
        st.header("⚙️ Status do Sistema")
        if st.button("🔍 Verificar Saúde"):
            with st.spinner("Verificando..."):
                health = asyncio.run(agent.check_health())
                col1, col2, col3 = st.columns(3)
                with col1:
                    if health["llm_connected"]:
                        st.success(f"✅ LLM: OK")
                    else:
                        st.error("❌ LLM: Offline")
                with col2:
                    if health["docker_available"]:
                        st.success("✅ Docker: OK")
                    else:
                        st.error("❌ Docker: Offline")
                with col3:
                    st.info(f"📊 Status: {health['status']}")
                
                with st.expander("📋 Detalhes"):
                    st.json(health)
        st.divider()
        st.header("⏱️ Execução Automática de Tarefas")
        recurring_desc = st.text_area(
            "Descrição da tarefa recorrente",
            value="Gerar função utilitária e testes unitários (ex: add(a,b))",
            height=80
        )
        recurring_count = st.number_input("Repetições", min_value=1, max_value=100, value=3)
        if st.button("▶️ Executar uma vez"):
            with st.spinner("Executando tarefa..."):
                try:
                    result = asyncio.run(agent.develop(recurring_desc, "python"))
                    if result["success"]:
                        st.success("✅ Tarefa concluída com sucesso")
                        st.code(result.get("code", ""))
                    else:
                        st.error("❌ Falha na execução")
                        for err in result.get("errors", []):
                            st.warning(err)
                except Exception as e:
                    st.error(f"Erro ao executar: {e}")

        if st.button("🔁 Executar Recorrente"):
            with st.spinner("Executando tarefas recorrentes..."):
                successes = 0
                failures = 0
                for i in range(int(recurring_count)):
                    try:
                        res = asyncio.run(agent.develop(recurring_desc, "python"))
                        if res.get("success"):
                            successes += 1
                        else:
                            failures += 1
                    except Exception:
                        failures += 1
                st.info(f"Concluído: {successes} sucesso(s), {failures} falha(s)")
        
        st.divider()
        st.header("📚 Tecnologias Suportadas")
        from dev_agent.config import SUPPORTED_TECHNOLOGIES
        for tech in SUPPORTED_TECHNOLOGIES:
            st.caption(f"• {tech}")
    
    tab1, tab2, tab3 = st.tabs(["🚀 Desenvolvimento", "⚡ Execução Rápida", "💬 Chat"])
    
    with tab1:
        st.header("🚀 Criar Código Automaticamente")
        col1, col2 = st.columns(2)
        
        with col1:
            description = st.text_area(
                "Descreva o que você quer criar:",
                height=100,
                placeholder="Ex: Uma função que calcula fibonacci recursivamente com memoization"
            )
        
        with col2:
            language = st.selectbox("Linguagem:", ["python", "javascript", "go", "rust"])
        
        if st.button("🚀 Desenvolver", type="primary", use_container_width=True):
            if description:
                with st.spinner("⏳ Gerando e testando código..."):
                    try:
                        result = asyncio.run(agent.develop(description, language))
                        if result["success"]:
                            st.success(f"✅ Código criado em {result['iterations']} iterações!")
                            st.code(result["code"], language=language)
                            if result.get("tests"):
                                with st.expander("🧪 Testes"):
                                    st.code(result["tests"], language=language)
                        else:
                            st.error("❌ Falha ao criar código")
                            for err in result["errors"]:
                                st.warning(f"⚠️ {err}")
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
            else:
                st.warning("⚠️ Digite uma descrição")
    
    with tab2:
        st.header("⚡ Executar Código Rapidamente")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            code = st.text_area(
                "Cole seu código:",
                height=200,
                key="quick_code",
                placeholder="import sys\nprint(f'Python {sys.version}')"
            )
        
        with col2:
            lang = st.selectbox("Linguagem:", ["python", "javascript"], key="quick_lang")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("▶️ Executar", use_container_width=True):
                if code:
                    with st.spinner("⏳ Executando..."):
                        try:
                            result = asyncio.run(agent.quick_run(code, lang))
                            if result["success"]:
                                st.success("✅ Executado com sucesso!")
                                st.code(result["output"])
                            else:
                                st.error("❌ Erro na execução")
                                st.code(result["errors"])
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")
                else:
                    st.warning("⚠️ Cole um código")
        
        with col2:
            if st.button("🔧 Auto-corrigir", use_container_width=True):
                if code:
                    with st.spinner("⏳ Corrigindo..."):
                        try:
                            result = asyncio.run(agent.fix_code(code, lang))
                            if result["success"]:
                                st.success(f"✅ Corrigido em {result['iterations']} iterações!")
                                st.code(result["fixed_code"], language=lang)
                            else:
                                st.error("❌ Não foi possível corrigir")
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")
                else:
                    st.warning("⚠️ Cole um código")
        
        with col3:
            if st.button("🧪 Testar", use_container_width=True):
                if code:
                    with st.spinner("⏳ Testando..."):
                        try:
                            result = asyncio.run(agent.test_code(code, lang))
                            if result["success"]:
                                st.success("✅ Testes passaram!")
                                st.code(result["test_output"])
                            else:
                                st.warning("⚠️ Testes falharam")
                                st.code(result["errors"])
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")
                else:
                    st.warning("⚠️ Cole um código")
    
    with tab3:
        st.header("💬 Chat com o Agente")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Exibir histórico
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        # Input do chat
        if prompt := st.chat_input("Digite sua mensagem..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("💭 Pensando..."):
                    try:
                        response = asyncio.run(agent.chat(prompt))
                        st.write(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    main()
