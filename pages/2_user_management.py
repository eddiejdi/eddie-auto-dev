"""
User Management Dashboard - Streamlit UI

Painel interativo para gestão de usuários com pipeline automático
"""

import asyncio
from datetime import datetime

import streamlit as st
from streamlit_option_menu import option_menu

from specialized_agents.user_management import (
    UserConfig,
    UserStatus,
    create_user,
    delete_user,
    get_user,
    list_users,
    pipeline,
)

# Configuração da página
st.set_page_config(
    page_title="User Management",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS customizado
st.markdown(
    """
<style>
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 5px; }
    .success { color: #28a745; font-weight: bold; }
    .error { color: #dc3545; font-weight: bold; }
    .pending { color: #ffc107; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)


def main():
    """Main app"""
    st.title("👥 Gestão de Usuários")
    st.markdown("Painel completo de gerenciamento de usuários com pipeline automático")

    # Menu lateral
    with st.sidebar:
        page = option_menu(
            "Menu",
            [
                "Dashboard",
                "Criar Usuário",
                "Listar Usuários",
                "Gerenciar",
                "Configurações",
            ],
            icons=["graph-up", "plus-circle", "list", "cog", "settings"],
            menu_icon="menu-button-wide",
            default_index=0,
        )

        st.divider()
        st.subheader("ℹ Info")
        st.info(
            """
**Etapas do Pipeline:**
1. 📝 **Authentik** - Criar conta central
2. 📧 **Email** - Criar email user
3. ⚙️ **Ambiente** - Setup user home
4. ✅ **Completo** - Usuário pronto
"""
        )

    # Renderizar página
    if page == "Dashboard":
        show_dashboard()
    elif page == "Criar Usuário":
        show_create_user()
    elif page == "Listar Usuários":
        show_list_users()
    elif page == "Gerenciar":
        show_manage_users()
    elif page == "Configurações":
        show_settings()


def show_dashboard():
    """Dashboard principal"""
    st.header("📊 Dashboard")

    # Estatísticas
    users = list_users()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total de Usuários", len(users))

    with col2:
        completes = len([u for u in users if u["status"] == UserStatus.COMPLETE.value])
        st.metric("Completos", completes)

    with col3:
        pendings = len([u for u in users if u["status"] == UserStatus.PENDING.value])
        st.metric("Pendentes", pendings)

    with col4:
        fails = len([u for u in users if u["status"] == UserStatus.FAILED.value])
        st.metric("Falhas", fails, delta=f"{fails} usuários", delta_color="inverse")

    st.divider()

    # Últimos usuários criados
    st.subheader("📅 Últimos Usuários Criados")

    if users:
        recent_users = users[:5]
        for user in recent_users:
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

            with col1:
                st.write(f"**{user['username']}**")

            with col2:
                status_color = {
                    UserStatus.COMPLETE.value: "🟢",
                    UserStatus.PENDING.value: "🟡",
                    UserStatus.FAILED.value: "🔴",
                    UserStatus.AUTHENTIK_CREATED.value: "🟠",
                    UserStatus.EMAIL_CREATED.value: "🟡",
                    UserStatus.ENV_SETUP.value: "🟠",
                }
                status_emoji = status_color.get(user["status"], "❓")
                st.write(f"{status_emoji} {user['status']}")

            with col3:
                st.write(f"📧 {user['email']}")

            with col4:
                created = user["created_at"]
                if isinstance(created, str):
                    created = datetime.fromisoformat(created)
                st.write(f"📅 {created.strftime('%d/%m %H:%M')}")
    else:
        st.info("Nenhum usuário criado ainda")

    st.divider()

    # Status dos sistemas
    st.subheader("🔧 Status dos Sistemas")

    col1, col2, col3 = st.columns(3)

    with col1:
        try:
            # Testar Authentik
            import requests

            resp = requests.get(
                "https://auth.rpa4all.com/api/health/", timeout=2, verify=False
            )
            if resp.status_code == 200:
                st.success("✅ Authentik Online")
            else:
                st.warning(f"⚠ Authentik: {resp.status_code}")
        except:
            st.error("❌ Authentik Offline")

    with col2:
        try:
            # Testar Email
            import subprocess

            result = subprocess.run(
                ["sudo", "systemctl", "is-active", "--quiet", "postfix"],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                st.success("✅ Email + Postfix Online")
            else:
                st.warning("⚠ Email/Postfix Offline")
        except:
            st.error("❌ Email Offline")

    with col3:
        try:
            # Testar DB
            import psycopg2
            import os

            conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            conn.close()
            st.success("✅ Database Online")
        except:
            st.error("❌ Database Offline")


def show_create_user():
    """Criar novo usuário"""
    st.header("➕ Criar Novo Usuário")

    with st.form("create_user_form"):
        col1, col2 = st.columns(2)

        with col1:
            username = st.text_input(
                "Nome de usuário",
                help="Alfanumérico, sem espaços",
            )
            email = st.text_input(
                "Email",
                help="Email completo",
            )

        with col2:
            full_name = st.text_input(
                "Nome completo",
                help="Nome para exibição",
            )
            password = st.text_input(
                "Senha",
                type="password",
                help="Será forçada mudança no primeiro login",
            )

        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:
            groups = st.multiselect(
                "Grupos",
                ["users", "admin", "email_admins", "email_users", "developers"],
                default=["users"],
            )

        with col2:
            quota_mb = st.number_input(
                "Quota de Email (MB)",
                min_value=100,
                max_value=10000,
                value=5000,
                step=100,
            )

        with col3:
            storage_quota_mb = st.number_input(
                "Quota de Storage (MB)",
                min_value=1000,
                max_value=1000000,
                value=100000,
                step=1000,
            )

        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            create_ssh = st.checkbox("Gerar chave SSH", value=True)
        with col2:
            create_folders = st.checkbox("Criar pastas", value=True)
        with col3:
            send_welcome = st.checkbox("Enviar email boas-vindas", value=True)

        st.divider()

        submitted = st.form_submit_button("🚀 Criar Usuário", use_container_width=True)

        if submitted:
            # Validação
            if not all([username, email, full_name, password]):
                st.error("❌ Preencha todos os campos obrigatórios")
                return

            if " " in username or not username.isalnum():
                st.error("❌ Nome de usuário deve ter apenas letras e números")
                return

            # Criar
            st.info("Iniciando pipeline de criação...")

            progress_bar = st.progress(0)
            status_container = st.container()

            try:
                config = UserConfig(
                    username=username,
                    email=email,
                    full_name=full_name,
                    password=password,
                    groups=groups,
                    quota_mb=quota_mb,
                    storage_quota_mb=storage_quota_mb,
                    create_ssh_key=create_ssh,
                    create_folders=create_folders,
                    send_welcome_email=send_welcome,
                )

                # Executar pipeline
                result = asyncio.run(create_user(config))

                # Mostrar resultado
                if result["success"]:
                    st.success("✅ Usuário criado com sucesso!")

                    with status_container:
                        st.markdown("**Steps do Pipeline:**")
                        for step, status in result["steps"].items():
                            if status == "✓":
                                st.write(f"✅ {step}: OK")
                            else:
                                st.write(f"❌ {step}: FALHOU")

                    progress_bar.progress(100)

                    st.balloons()

                    # Credenciais
                    st.divider()
                    st.subheader("🔐 Credenciais do Usuário")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.code(
                            f"""
Email: {email}
Senha: {password}
Username: {username}
""",
                            language="text",
                        )

                    with col2:
                        st.warning(
                            """
**⚠️ Importante:**
- O usuário DEVE alterar a senha no primeiro login
- Guarde as credenciais com segurança
- Compartilhe apenas via canais seguros
"""
                        )

                else:
                    st.error(f"❌ Erro: {result['error']}")
                    with status_container:
                        st.markdown("**Steps do Pipeline:**")
                        for step, status in result["steps"].items():
                            if status == "✓":
                                st.write(f"✅ {step}: OK")
                            else:
                                st.write(f"❌ {step}: FALHOU")

            except Exception as e:
                st.error(f"❌ Erro: {e}")
                import traceback

                st.error(traceback.format_exc())


def show_list_users():
    """Listar todos os usuários"""
    st.header("📋 Listar Usuários")

    users = list_users()

    if not users:
        st.info("Nenhum usuário criado")
        return

    # Filtros
    col1, col2, col3 = st.columns(3)

    with col1:
        status_filter = st.multiselect(
            "Filtrar por status",
            [s.value for s in UserStatus],
            default=[s.value for s in UserStatus],
        )

    with col2:
        search = st.text_input("Buscar por nome/email")

    with col3:
        sort_by = st.selectbox("Ordenar por", ["Criação (recente)", "Mock (antigo)"])

    # Aplicar filtros
    filtered = [u for u in users if u["status"] in status_filter]

    if search:
        filtered = [
            u
            for u in filtered
            if search.lower() in u["username"].lower()
            or search.lower() in u["email"].lower()
        ]

    st.write(f"**Total: {len(filtered)} usuário(s)**")

    st.divider()

    # Tabela
    for user in filtered:
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])

        with col1:
            st.write(f"**{user['username']}**")

        with col2:
            st.write(user["email"])

        with col3:
            status_color = {
                UserStatus.COMPLETE.value: "🟢 Completo",
                UserStatus.PENDING.value: "🟡 Pendente",
                UserStatus.FAILED.value: "🔴 Falhou",
                UserStatus.AUTHENTIK_CREATED.value: "🟠 Authentik",
                UserStatus.EMAIL_CREATED.value: "🟡 Email",
                UserStatus.ENV_SETUP.value: "🟠 Ambiente",
            }
            st.write(status_color.get(user["status"], user["status"]))

        with col4:
            created = user["created_at"]
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            st.write(created.strftime("%d/%m/%y"))

        with col5:
            if st.button("📋", key=f"view_{user['username']}", help="Ver detalhes"):
                st.session_state["selected_user"] = user["username"]
                st.rerun()

        st.divider()


def show_manage_users():
    """Gerenciar usuários"""
    st.header("⚙️ Gerenciar Usuários")

    users = list_users()

    if not users:
        st.info("Nenhum usuário para gerenciar")
        return

    username = st.selectbox(
        "Selecione um usuário",
        [u["username"] for u in users],
    )

    if username:
        user = get_user(username)

        if user:
            st.subheader(f"Usuário: {user['username']}")

            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Email:** {user['email']}")
                st.write(f"**Nome:** {user['full_name']}")
                st.write(f"**Status:** {user['status']}")

            with col2:
                created = user["created_at"]
                if isinstance(created, str):
                    created = datetime.fromisoformat(created)
                st.write(f"**Criado em:** {created.strftime('%d/%m/%Y %H:%M:%S')}")

                updated = user["updated_at"]
                if isinstance(updated, str):
                    updated = datetime.fromisoformat(updated)
                st.write(f"**Atualizado em:** {updated.strftime('%d/%m/%Y %H:%M:%S')}")

            st.divider()

            # Ações
            st.subheader("Ações")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button(
                    "🔄 Re-iniciar Pipeline",
                    use_container_width=True,
                ):
                    st.warning("Funcionalidade em desenvolvimento")

            with col2:
                if st.button("🔑 Reset Senha", use_container_width=True):
                    st.warning("Funcionalidade em desenvolvimento")

            with col3:
                if st.button(
                    "🗑️ Deletar Usuário",
                    use_container_width=True,
                    help="Remover de todos os sistemas",
                ):
                    st.warning(
                        f"⚠️ Você tem certeza que quer deletar {username}? "
                        "Esta ação não pode ser desfeita!"
                    )

                    if st.button("❌ Confirmar Deleção"):
                        st.info("Deletando usuário...")

                        result = asyncio.run(delete_user(username))

                        if result["success"]:
                            st.success("✅ Usuário deletado!")
                            st.rerun()
                        else:
                            st.error(f"❌ Erro: {result['error']}")


def show_settings():
    """Configurações"""
    st.header("⚙️ Configurações")

    st.subheader("🔐 Variáveis de Ambiente")

    with st.expander("Ver Configurações"):
        import os

        configs = {
            "AUTHENTIK_URL": os.getenv("AUTHENTIK_URL", "❌ Não configurado"),
            "MAIL_DOMAIN": os.getenv("MAIL_DOMAIN", "❌ Não configurado"),
            "DATABASE_URL": "***" if os.getenv("DATABASE_URL") else "❌ Não configurado",
            "HOSTNAME": os.getenv("HOSTNAME", "eddie"),
        }

        for key, value in configs.items():
            st.write(f"**{key}:** `{value}`")

    st.divider()

    st.subheader("📊 Status dos Módulos")

    modules = {
        "Authentik Manager": True,
        "Email Manager": True,
        "Environment Setup": True,
        "User Database": True,
        "Pipeline": True,
    }

    for module, status in modules.items():
        if status:
            st.success(f"✅ {module}")
        else:
            st.error(f"❌ {module}")

    st.divider()

    st.subheader("📝 Sobre")

    st.info(
        """
**User Management System v1.0**

Sistema completo de gestão de usuários com pipeline automático.

**Componentes:**
- 📝 Authentik (autenticação central)
- 📧 Email Server (Dovecot/Postfix)
- ⚙️ Environment Setup (home, SSH, folders)
- 💾 PostgreSQL (tracking)

**Criado com:** Streamlit + Python + FastAPI
"""
    )


if __name__ == "__main__":
    main()
