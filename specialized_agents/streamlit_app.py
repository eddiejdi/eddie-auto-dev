"""
Interface Streamlit para Agentes Especializados
Dashboard para gerenciar agentes, projetos e interagir com GitHub
"""
import streamlit as st
import asyncio
import json
import os
import subprocess
import requests
from datetime import datetime
from pathlib import Path
import sys

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from specialized_agents import (
    AgentManager,
    get_agent_manager,
    DockerOrchestrator,
    FileManager,
    CleanupService
)
from specialized_agents.language_agents import AGENT_CLASSES


# ================== Configuração da Página ==================
st.set_page_config(
    page_title="🤖 Agentes Programadores",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================== Estado Global ==================
if "manager" not in st.session_state:
    st.session_state.manager = get_agent_manager()
    asyncio.run(st.session_state.manager.initialize())

if "current_agent" not in st.session_state:
    st.session_state.current_agent = None

if "messages" not in st.session_state:
    st.session_state.messages = []


# ================== Funções Auxiliares ==================
def run_async(coro):
    """Executa coroutine de forma síncrona"""
    return asyncio.run(coro)


# ================== Configurações do Home Lab ==================
SERVER_IP = "192.168.15.2"
OLLAMA_URL = f"http://{SERVER_IP}:11434"
WAHA_URL = f"http://{SERVER_IP}:3001"
OPENWEBUI_URL = f"http://{SERVER_IP}:3000"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

HOMELAB_SERVICES = [
    ("eddie-telegram-bot", "Telegram Bot", "Bot Telegram para comandos"),
    ("eddie-whatsapp-bot", "WhatsApp Bot", "Bot WhatsApp via WAHA"),
    ("eddie-calendar", "Calendar", "Lembretes Google Calendar"),
    ("specialized-agents-api", "Agents API", "API de agentes especializados"),
    ("btc-trading-engine", "BTC Engine", "Trading engine Bitcoin"),
    ("btc-webui-api", "BTC WebUI", "API para Open WebUI"),
    ("github-agent", "GitHub Agent", "Automação GitHub"),
    ("ollama", "Ollama", "Servidor LLM"),
    ("waha", "WAHA", "API WhatsApp"),
]

def check_http_service(url: str, timeout: int = 3) -> bool:
    """Verifica se um serviço HTTP está online"""
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code in [200, 301, 302]
    except:
        return False

def check_systemd_service(service_name: str) -> dict:
    """Verifica status de um serviço systemd"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True, timeout=5
        )
        is_active = result.stdout.strip() == "active"
        return {"active": is_active, "state": result.stdout.strip()}
    except Exception as e:
        return {"active": False, "state": "error", "error": str(e)}

def control_systemd_service(service_name: str, action: str) -> tuple:
    """Controla um serviço systemd (start/stop/restart)"""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, service_name],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stderr or "OK"
    except Exception as e:
        return False, str(e)

def get_ollama_models():
    """Lista modelos do Ollama"""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if r.status_code == 200:
            return r.json().get('models', [])
    except:
        pass
    return []

def get_system_stats():
    """Obtém estatísticas do sistema"""
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
        total_mem = meminfo.get('MemTotal', 0) / 1024 / 1024
        free_mem = meminfo.get('MemAvailable', 0) / 1024 / 1024
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        disk_line = result.stdout.strip().split('\n')[1].split()
        return {
            "cpu_load": load,
            "mem_total_gb": round(total_mem, 1),
            "mem_used_gb": round(total_mem - free_mem, 1),
            "mem_percent": round((total_mem - free_mem) / total_mem * 100, 1) if total_mem else 0,
            "disk_percent": disk_line[4] if len(disk_line) > 4 else "?"
        }
    except:
        return {"cpu_load": ["?", "?", "?"], "mem_total_gb": 0, "mem_used_gb": 0, "disk_percent": "?"}


# ================== Sidebar ==================
with st.sidebar:
    st.title("🤖 Agentes Especializados")
    st.markdown("---")
    
    # Seleção de Linguagem
    st.subheader("📝 Selecionar Agente")
    languages = list(AGENT_CLASSES.keys())
    selected_lang = st.selectbox(
        "Linguagem",
        languages,
        format_func=lambda x: f"{x.upper()} Expert"
    )
    
    if st.button("🚀 Ativar Agente", use_container_width=True):
        agent = st.session_state.manager.get_or_create_agent(selected_lang)
        st.session_state.current_agent = agent
        st.success(f"Agente {agent.name} ativado!")
    
    st.markdown("---")
    
    # Status do Sistema
    st.subheader("📊 Status")
    if st.button("🔄 Atualizar Status", use_container_width=True):
        status = run_async(st.session_state.manager.get_system_status())
        st.json(status)
    
    # Agentes Ativos
    active = st.session_state.manager.list_active_agents()
    if active:
        st.write("**Agentes Ativos:**")
        for agent in active:
            st.write(f"• {agent['name']}")
    
    st.markdown("---")
    
    # Ações Rápidas
    st.subheader("⚡ Ações Rápidas")
    
    if st.button("🧹 Executar Limpeza", use_container_width=True):
        with st.spinner("Executando limpeza..."):
            report = run_async(st.session_state.manager.run_cleanup())
            st.success(f"Limpeza concluída! Espaço liberado: {report.get('space_freed_mb', 0):.2f} MB")
    
    if st.button("📦 Ver Containers", use_container_width=True):
        containers = st.session_state.manager.docker.list_containers()
        if containers:
            st.json(containers)
        else:
            st.info("Nenhum container ativo")


# ================== Área Principal ==================
st.title("🤖 Agentes Programadores Especializados")
st.markdown("Desenvolva em qualquer linguagem com agentes de IA especializados")

# Tabs principais
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "💬 Chat", "📁 Upload/Download", "🐳 Docker", "📚 RAG", "🐙 GitHub", "⚙️ Configurações", "🖥️ Home Lab"
])


# ================== Tab Chat ==================
with tab1:
    st.header("💬 Chat com Agente")
    
    if st.session_state.current_agent:
        agent = st.session_state.current_agent
        st.info(f"**Agente Ativo:** {agent.name}")
        st.write(f"**Capacidades:** {', '.join(agent.capabilities[:5])}...")
        
        # Área de Chat
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # Input
        if prompt := st.chat_input("Descreva o que você quer desenvolver..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Gerando código..."):
                    # Gerar código
                    code = run_async(agent.generate_code(prompt))
                    st.code(code, language=agent.language)
                    
                    # Gerar testes
                    with st.expander("📋 Testes Gerados"):
                        tests = run_async(agent.generate_tests(code, prompt))
                        st.code(tests, language=agent.language)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"```{agent.language}\n{code}\n```"
                    })
        
        # Criar Projeto Completo
        st.markdown("---")
        st.subheader("🏗️ Criar Projeto Completo")
        
        col1, col2 = st.columns(2)
        with col1:
            project_desc = st.text_area(
                "Descrição do Projeto",
                placeholder="Descreva o projeto que você quer criar..."
            )
        with col2:
            project_name = st.text_input("Nome do Projeto (opcional)")
        
        if st.button("🚀 Criar Projeto", type="primary"):
            if project_desc:
                with st.spinner("Criando projeto..."):
                    result = run_async(st.session_state.manager.create_project(
                        agent.language,
                        project_desc,
                        project_name
                    ))
                    
                    if result.get("success"):
                        st.success("Projeto criado com sucesso!")
                        with st.expander("📄 Detalhes"):
                            st.json(result)
                    else:
                        st.error(f"Erro: {result.get('task', {}).get('errors', [])}")
            else:
                st.warning("Por favor, descreva o projeto")
    else:
        st.warning("⚠️ Selecione um agente no menu lateral para começar")


# ================== Tab Upload/Download ==================
with tab2:
    st.header("📁 Upload / Download de Arquivos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📤 Upload")
        
        upload_type = st.radio("Tipo", ["Arquivo Único", "Projeto ZIP"])
        
        if upload_type == "Arquivo Único":
            uploaded_file = st.file_uploader(
                "Escolha um arquivo",
                type=["py", "js", "ts", "go", "rs", "java", "cs", "php", "json", "yaml", "txt", "md"]
            )
            
            upload_lang = st.selectbox("Linguagem (auto-detect)", ["auto"] + languages)
            auto_run = st.checkbox("Executar automaticamente")
            
            if uploaded_file and st.button("📤 Fazer Upload"):
                with st.spinner("Processando..."):
                    content = uploaded_file.read()
                    lang = None if upload_lang == "auto" else upload_lang
                    
                    result = run_async(st.session_state.manager.upload_and_process(
                        content,
                        uploaded_file.name,
                        lang,
                        auto_run
                    ))
                    
                    st.success("Upload concluído!")
                    st.json(result)
        
        else:  # ZIP
            uploaded_zip = st.file_uploader("Escolha um arquivo ZIP", type=["zip"])
            zip_project_name = st.text_input("Nome do Projeto")
            auto_build = st.checkbox("Build automático")
            
            if uploaded_zip and st.button("📤 Upload ZIP"):
                with st.spinner("Extraindo e processando..."):
                    result = run_async(st.session_state.manager.upload_zip_project(
                        uploaded_zip.read(),
                        zip_project_name,
                        auto_build
                    ))
                    
                    st.success("Projeto importado!")
                    st.json(result)
    
    with col2:
        st.subheader("📥 Download")
        
        # Listar projetos
        download_lang = st.selectbox("Filtrar por linguagem", ["Todas"] + languages, key="dl_lang")
        
        if st.button("🔄 Listar Projetos"):
            from specialized_agents.config import PROJECTS_DIR
            
            projects = []
            search_dir = PROJECTS_DIR
            if download_lang != "Todas":
                search_dir = PROJECTS_DIR / download_lang
            
            if search_dir.exists():
                for lang_dir in search_dir.iterdir():
                    if lang_dir.is_dir():
                        if download_lang == "Todas":
                            for proj in lang_dir.iterdir():
                                if proj.is_dir():
                                    projects.append(f"{lang_dir.name}/{proj.name}")
                        else:
                            projects.append(lang_dir.name)
            
            st.session_state.available_projects = projects
        
        if "available_projects" in st.session_state:
            selected_project = st.selectbox(
                "Selecione projeto",
                st.session_state.available_projects
            )
            
            if selected_project and st.button("📥 Download como ZIP"):
                parts = selected_project.split("/")
                if len(parts) == 2:
                    lang, name = parts
                else:
                    lang = download_lang if download_lang != "Todas" else "python"
                    name = parts[0]
                
                zip_data = run_async(st.session_state.manager.download_project(lang, name))
                
                if zip_data:
                    st.download_button(
                        "💾 Salvar ZIP",
                        zip_data,
                        f"{name}.zip",
                        "application/zip"
                    )
                else:
                    st.error("Projeto não encontrado")


# ================== Tab Docker ==================
with tab3:
    st.header("🐳 Gerenciamento Docker")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Containers Ativos")
        
        containers = st.session_state.manager.docker.list_containers()
        
        if containers:
            for container in containers:
                with st.expander(f"🐳 {container['name']} ({container['status']})"):
                    st.json(container)
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        if container['status'] == 'running':
                            if st.button("⏹️ Parar", key=f"stop_{container['container_id']}"):
                                run_async(st.session_state.manager.docker.stop_container(
                                    container['container_id']
                                ))
                                st.rerun()
                        else:
                            if st.button("▶️ Iniciar", key=f"start_{container['container_id']}"):
                                run_async(st.session_state.manager.docker.start_container(
                                    container['container_id']
                                ))
                                st.rerun()
                    
                    with col_b:
                        if st.button("📋 Logs", key=f"logs_{container['container_id']}"):
                            logs = run_async(st.session_state.manager.docker.get_logs(
                                container['container_id']
                            ))
                            st.code(logs)
                    
                    with col_c:
                        if st.button("🗑️ Remover", key=f"rm_{container['container_id']}"):
                            run_async(st.session_state.manager.docker.remove_container(
                                container['container_id'],
                                backup=True
                            ))
                            st.rerun()
        else:
            st.info("Nenhum container ativo")
    
    with col2:
        st.subheader("Criar Container")
        
        new_lang = st.selectbox("Linguagem", languages, key="docker_lang")
        new_code = st.text_area("Código inicial", height=200)
        new_deps = st.text_input("Dependências (separadas por vírgula)")
        
        if st.button("🐳 Criar Container"):
            if new_code:
                deps = [d.strip() for d in new_deps.split(",") if d.strip()]
                
                with st.spinner("Criando container..."):
                    result = run_async(st.session_state.manager.docker.create_project(
                        new_lang,
                        new_code,
                        deps
                    ))
                    
                    if result.get("success"):
                        st.success(f"Container criado: {result['container_id']}")
                        st.json(result)
                    else:
                        st.error(result.get("error"))
            else:
                st.warning("Insira o código inicial")
        
        st.markdown("---")
        
        # Executar Código
        st.subheader("Executar Código")
        
        exec_container = st.selectbox(
            "Container",
            [c['container_id'] for c in containers] if containers else []
        )
        exec_code = st.text_area("Código para executar", key="exec_code", height=150)
        
        if st.button("▶️ Executar") and exec_container:
            with st.spinner("Executando..."):
                result = run_async(st.session_state.manager.docker.exec_command(
                    exec_container,
                    f"python -c '{exec_code}'" if "python" in exec_container else exec_code
                ))
                
                st.code(result.stdout or result.stderr)


# ================== Tab RAG ==================
with tab4:
    st.header("📚 RAG - Base de Conhecimento")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔍 Buscar")
        
        search_query = st.text_input("Buscar no RAG")
        search_lang = st.selectbox("Filtrar linguagem", ["Todas"] + languages, key="rag_lang")
        
        if st.button("🔍 Buscar") and search_query:
            with st.spinner("Buscando..."):
                if search_lang == "Todas":
                    results = run_async(
                        st.session_state.manager.search_rag_all_languages(search_query)
                    )
                else:
                    from specialized_agents.rag_manager import RAGManagerFactory
                    manager = RAGManagerFactory.get_manager(search_lang)
                    results = run_async(manager.search_with_metadata(search_query))
                
                if results:
                    for i, result in enumerate(results, 1):
                        with st.expander(f"Resultado {i} - Score: {result.get('score', 0):.3f}"):
                            st.code(result.get("content", "")[:1000])
                            st.json(result.get("metadata", {}))
                else:
                    st.info("Nenhum resultado encontrado")
    
    with col2:
        st.subheader("📝 Indexar")
        
        index_type = st.radio("Tipo de Conteúdo", ["Código", "Documentação", "Conversa"])
        index_lang = st.selectbox("Linguagem", languages, key="index_lang")
        
        if index_type == "Código":
            index_code = st.text_area("Código", height=200)
            index_desc = st.text_input("Descrição")
            
            if st.button("📥 Indexar Código"):
                from specialized_agents.rag_manager import RAGManagerFactory
                manager = RAGManagerFactory.get_manager(index_lang)
                
                success = run_async(manager.index_code(
                    index_code, index_lang, index_desc
                ))
                
                if success:
                    st.success("Código indexado!")
                else:
                    st.error("Erro ao indexar")
        
        elif index_type == "Documentação":
            index_title = st.text_input("Título")
            index_content = st.text_area("Conteúdo", height=200)
            
            if st.button("📥 Indexar Documentação"):
                from specialized_agents.rag_manager import RAGManagerFactory
                manager = RAGManagerFactory.get_manager(index_lang)
                
                success = run_async(manager.index_documentation(
                    index_content, index_title
                ))
                
                if success:
                    st.success("Documentação indexada!")
        
        else:  # Conversa
            index_question = st.text_input("Pergunta")
            index_answer = st.text_area("Resposta", height=150)
            
            if st.button("📥 Indexar Conversa"):
                from specialized_agents.rag_manager import RAGManagerFactory
                manager = RAGManagerFactory.get_manager(index_lang)
                
                success = run_async(manager.index_conversation(
                    index_question, index_answer
                ))
                
                if success:
                    st.success("Conversa indexada!")
        
        # Estatísticas
        st.markdown("---")
        st.subheader("📊 Estatísticas")
        
        if st.button("📊 Ver Estatísticas RAG"):
            from specialized_agents.rag_manager import RAGManagerFactory
            
            stats = {}
            for lang in languages:
                try:
                    manager = RAGManagerFactory.get_manager(lang)
                    stats[lang] = run_async(manager.get_stats())
                except:
                    pass
            
            st.json(stats)


# ================== Tab GitHub ==================
with tab5:
    st.header("🐙 Integração GitHub")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 Repositórios")
        
        github_owner = st.text_input("Owner/Organização")
        
        if st.button("📋 Listar Repos") and github_owner:
            with st.spinner("Buscando..."):
                result = run_async(st.session_state.manager.github_client.list_repos(github_owner))
                
                if result.success:
                    repos = result.data if isinstance(result.data, list) else []
                    for repo in repos[:10]:
                        st.write(f"• **{repo.get('name')}** - {repo.get('description', 'Sem descrição')[:50]}")
                else:
                    st.error(result.error)
        
        st.markdown("---")
        
        # Criar Repo
        st.subheader("➕ Criar Repositório")
        
        new_repo_name = st.text_input("Nome do Repositório")
        new_repo_desc = st.text_input("Descrição")
        new_repo_lang = st.selectbox("Linguagem Principal", languages, key="new_repo_lang")
        new_repo_private = st.checkbox("Privado")
        
        if st.button("🚀 Criar Repositório"):
            if new_repo_name:
                with st.spinner("Criando..."):
                    result = run_async(st.session_state.manager.github_client.create_repo(
                        new_repo_name, new_repo_desc, new_repo_private, new_repo_lang
                    ))
                    
                    if result.success:
                        st.success(f"Repositório criado!")
                        st.json(result.data)
                    else:
                        st.error(result.error)
    
    with col2:
        st.subheader("📤 Push Projeto Local")
        
        from specialized_agents.config import PROJECTS_DIR
        
        # Listar projetos locais
        local_projects = []
        if PROJECTS_DIR.exists():
            for lang_dir in PROJECTS_DIR.iterdir():
                if lang_dir.is_dir():
                    for proj in lang_dir.iterdir():
                        if proj.is_dir():
                            local_projects.append(f"{lang_dir.name}/{proj.name}")
        
        push_project = st.selectbox("Projeto Local", local_projects)
        push_repo_name = st.text_input("Nome no GitHub (deixe vazio para usar nome do projeto)")
        push_desc = st.text_input("Descrição do Repositório")
        
        if st.button("📤 Push para GitHub") and push_project:
            parts = push_project.split("/")
            lang, name = parts[0], parts[1]
            
            with st.spinner("Fazendo push..."):
                result = run_async(st.session_state.manager.push_to_github(
                    lang, name, push_repo_name or name, push_desc
                ))
                
                if result.get("success"):
                    st.success("Projeto enviado para GitHub!")
                    st.json(result)
                else:
                    st.error(result.get("error") or result.get("warning"))
        
        st.markdown("---")
        
        # Issues
        st.subheader("📝 Issues")
        
        issue_owner = st.text_input("Owner", key="issue_owner")
        issue_repo = st.text_input("Repositório", key="issue_repo")
        
        if st.button("📋 Listar Issues"):
            if issue_owner and issue_repo:
                result = run_async(st.session_state.manager.github_client.list_issues(
                    issue_owner, issue_repo
                ))
                
                if result.success:
                    for issue in (result.data or [])[:10]:
                        st.write(f"• #{issue.get('number')} - {issue.get('title')}")
                else:
                    st.error(result.error)


# ================== Tab Configurações ==================
with tab6:
    st.header("⚙️ Configurações")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🧹 Limpeza Automática")
        
        from specialized_agents.config import CLEANUP_CONFIG
        
        retention_days = st.number_input(
            "Dias de Retenção de Backup",
            value=CLEANUP_CONFIG["backup_retention_days"],
            min_value=1,
            max_value=30
        )
        
        cleanup_interval = st.number_input(
            "Intervalo de Limpeza (horas)",
            value=CLEANUP_CONFIG["cleanup_interval_hours"],
            min_value=1,
            max_value=168
        )
        
        auto_cleanup = st.checkbox(
            "Limpeza Automática Habilitada",
            value=CLEANUP_CONFIG["auto_cleanup_enabled"]
        )
        
        if st.button("💾 Salvar Configurações"):
            st.session_state.manager.cleanup_service.backup_retention_days = retention_days
            st.session_state.manager.cleanup_service.cleanup_interval_hours = cleanup_interval
            st.session_state.manager.cleanup_service.auto_cleanup_enabled = auto_cleanup
            st.success("Configurações salvas!")
        
        st.markdown("---")
        
        st.subheader("📊 Uso de Armazenamento")
        
        if st.button("📊 Verificar Armazenamento"):
            storage = run_async(st.session_state.manager.cleanup_service.get_storage_status())
            
            for key, info in storage.items():
                if isinstance(info, dict) and "size_mb" in info:
                    st.metric(key.upper(), f"{info['size_mb']:.2f} MB")
    
    with col2:
        st.subheader("🔧 LLM")
        
        from specialized_agents.config import LLM_CONFIG
        
        st.text_input("URL do Ollama", value=LLM_CONFIG["base_url"], disabled=True)
        st.text_input("Modelo", value=LLM_CONFIG["model"], disabled=True)
        
        st.markdown("---")
        
        st.subheader("📦 Backups")
        
        backup_type = st.selectbox("Tipo", ["projects", "containers", "files"])
        
        if st.button("📋 Listar Backups"):
            backups = st.session_state.manager.cleanup_service.list_backups(backup_type)
            
            if backups:
                for backup in backups[:10]:
                    with st.expander(backup["name"]):
                        st.write(f"**Tamanho:** {backup['size_mb']:.2f} MB")
                        st.json(backup.get("metadata", {}))
                        
                        if st.button("🔄 Restaurar", key=f"restore_{backup['path']}"):
                            success = run_async(
                                st.session_state.manager.cleanup_service.restore_backup(
                                    backup["path"]
                                )
                            )
                            if success:
                                st.success("Backup restaurado!")
            else:
                st.info("Nenhum backup encontrado")


# ================== Tab Home Lab ==================
with tab7:
    st.header("🖥️ Home Lab Control Panel")
    
    # Métricas do Sistema
    stats = get_system_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🖥️ CPU Load", stats.get('cpu_load', ['?'])[0])
    with col2:
        st.metric("💾 RAM", f"{stats.get('mem_used_gb', 0)}/{stats.get('mem_total_gb', 0)} GB")
    with col3:
        st.metric("💿 Disco", stats.get('disk_percent', '?'))
    with col4:
        st.metric("🦙 Modelos", len(get_ollama_models()))
    
    st.markdown("---")
    
    # Status Rápido
    st.subheader("⚡ Status dos Serviços Principais")
    
    quick_services = [
        ("Ollama", f"{OLLAMA_URL}/api/tags"),
        ("Open WebUI", OPENWEBUI_URL),
        ("WAHA", f"{WAHA_URL}/api/health"),
    ]
    
    qcols = st.columns(len(quick_services))
    for i, (name, url) in enumerate(quick_services):
        with qcols[i]:
            is_up = check_http_service(url)
            st.markdown(f"**{name}**: {'🟢 Online' if is_up else '🔴 Offline'}")
    
    st.markdown("---")
    
    # Gerenciamento de Serviços
    st.subheader("🔧 Gerenciamento de Serviços")
    
    for systemd, name, desc in HOMELAB_SERVICES:
        status = check_systemd_service(systemd)
        is_active = status.get("active", False)
        
        with st.expander(f"{'🟢' if is_active else '🔴'} {name} - {desc}"):
            col_a, col_b = st.columns([3, 1])
            
            with col_a:
                st.markdown(f"- **Serviço:** `{systemd}`")
                st.markdown(f"- **Estado:** `{status.get('state', 'unknown')}`")
            
            with col_b:
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("▶️", key=f"start_{systemd}", help="Iniciar"):
                        ok, msg = control_systemd_service(systemd, "start")
                        st.toast("✅ Iniciado!" if ok else f"❌ {msg}")
                with c2:
                    if st.button("⏹️", key=f"stop_{systemd}", help="Parar"):
                        ok, msg = control_systemd_service(systemd, "stop")
                        st.toast("✅ Parado!" if ok else f"❌ {msg}")
                with c3:
                    if st.button("🔄", key=f"restart_{systemd}", help="Reiniciar"):
                        ok, msg = control_systemd_service(systemd, "restart")
                        st.toast("✅ Reiniciado!" if ok else f"❌ {msg}")
    
    st.markdown("---")
    
    # Configurações e Links
    col_cfg1, col_cfg2 = st.columns(2)
    
    with col_cfg1:
        st.subheader("🌐 URLs & Portas")
        st.markdown(f"""
        | Serviço | URL | Status |
        |---------|-----|--------|
        | Ollama | [{SERVER_IP}:11434]({OLLAMA_URL}) | {'🟢' if check_http_service(f'{OLLAMA_URL}/api/tags') else '🔴'} |
        | Open WebUI | [{SERVER_IP}:3000]({OPENWEBUI_URL}) | {'🟢' if check_http_service(OPENWEBUI_URL) else '🔴'} |
        | WAHA | [{SERVER_IP}:3001]({WAHA_URL}/dashboard) | {'🟢' if check_http_service(f'{WAHA_URL}/api/health') else '🔴'} |
        | Agents API | [{SERVER_IP}:8502](http://{SERVER_IP}:8502) | 🟢 |
        | BTC Engine | [{SERVER_IP}:8511](http://{SERVER_IP}:8511) | {'🟢' if check_http_service(f'http://{SERVER_IP}:8511/health') else '🔴'} |
        """)
    
    with col_cfg2:
        st.subheader("📁 Configurações")
        st.markdown(f"""
        - **Servidor:** `{SERVER_IP}`
        - **Usuário:** `homelab`
        - **Projeto:** `/home/homelab/myClaude`
        - **GitHub:** [eddiejdi/eddie-auto-dev](https://github.com/eddiejdi/eddie-auto-dev)
        """)
        
        st.markdown("**Integrações:**")
        st.markdown("""
        - ✅ Telegram Bot
        - ✅ WhatsApp (WAHA)
        - ✅ Google Calendar
        - ✅ Gmail
        - ✅ GitHub
        - ✅ KuCoin Trading
        """)
    
    st.markdown("---")
    
    # Modelos Ollama
    st.subheader("🦙 Modelos Ollama")
    
    models = get_ollama_models()
    if models:
        model_cols = st.columns(4)
        for i, model in enumerate(models):
            with model_cols[i % 4]:
                name = model.get('name', 'unknown')
                size = model.get('size', 0) / (1024**3)
                st.markdown(f"**{name}**")
                st.caption(f"{size:.1f} GB")
    else:
        st.warning("Ollama offline ou sem modelos")


# ================== Footer ==================
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: gray;'>
    🤖 Agentes Programadores Especializados v1.0 | 
    🖥️ Home Lab: {SERVER_IP} |
    Powered by Ollama |
    {datetime.now().strftime('%H:%M:%S')}
    </div>
    """,
    unsafe_allow_html=True
)
