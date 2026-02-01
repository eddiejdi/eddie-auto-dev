#!/usr/bin/env python3
"""
🖥️ Home Lab Control Panel - Dashboard Centralizado
Painel de controle para gerenciar todos os serviços e configurações
"""

import streamlit as st
import requests
import subprocess
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dashboard.config import (
        SERVER,
        SERVICES,
        PORTS,
        URLS,
        OLLAMA_MODELS,
        INTEGRATIONS,
    )
except ImportError:
    # Fallback se não conseguir importar
    pass

# ================== CONFIGURAÇÃO ==================
st.set_page_config(
    page_title="🖥️ Home Lab Control Panel",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================== CONFIGURAÇÕES HARDCODED ==================
SERVER_IP = "192.168.15.2"
OLLAMA_URL = f"http://{SERVER_IP}:11434"
WAHA_URL = f"http://{SERVER_IP}:3001"
OPENWEBUI_URL = f"http://{SERVER_IP}:3000"

from tools.secrets_loader import get_telegram_token, get_telegram_chat_id

# Enforce retrieval of secrets from the repo cofre
try:
    TELEGRAM_TOKEN = get_telegram_token()
except Exception:
    TELEGRAM_TOKEN = ""

try:
    TELEGRAM_CHAT_ID = get_telegram_chat_id()
except Exception:
    TELEGRAM_CHAT_ID = ""

# ================== CSS ==================
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 20px 0;
    }
    .service-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        border-left: 4px solid #667eea;
    }
    .status-online { color: #00ff88; font-weight: bold; }
    .status-offline { color: #ff4444; font-weight: bold; }
    .status-unknown { color: #ffaa00; font-weight: bold; }
    .metric-big {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
    }
    .config-section {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .quick-action {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 10px;
        color: white;
        padding: 10px 20px;
        margin: 5px;
        cursor: pointer;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ================== FUNÇÕES UTILITÁRIAS ==================
def check_service(url: str, timeout: int = 5) -> bool:
    """Verifica se um serviço está online"""
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
            capture_output=True,
            text=True,
            timeout=5,
        )
        is_active = result.stdout.strip() == "active"

        # Pegar mais detalhes
        result2 = subprocess.run(
            [
                "systemctl",
                "show",
                service_name,
                "--property=ActiveState,SubState,MainPID",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        props = {}
        for line in result2.stdout.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v

        return {
            "active": is_active,
            "state": props.get("ActiveState", "unknown"),
            "substate": props.get("SubState", "unknown"),
            "pid": props.get("MainPID", "0"),
        }
    except Exception as e:
        return {"active": False, "state": "error", "error": str(e)}


def control_service(service_name: str, action: str) -> tuple:
    """Controla um serviço systemd (start/stop/restart)"""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, service_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stderr or "OK"
    except Exception as e:
        return False, str(e)


def get_ollama_models():
    """Lista modelos do Ollama"""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if r.status_code == 200:
            return r.json().get("models", [])
    except:
        pass
    return []


def get_system_stats():
    """Obtém estatísticas do sistema"""
    try:
        # CPU
        with open("/proc/loadavg", "r") as f:
            load = f.read().split()[:3]

        # Memory
        with open("/proc/meminfo", "r") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]
                    meminfo[key] = int(value)

        total_mem = meminfo.get("MemTotal", 0) / 1024 / 1024
        free_mem = meminfo.get("MemAvailable", 0) / 1024 / 1024
        used_mem = total_mem - free_mem

        # Disk
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        disk_line = result.stdout.strip().split("\n")[1].split()
        disk_used = disk_line[2]
        disk_total = disk_line[1]
        disk_percent = disk_line[4]

        return {
            "cpu_load": load,
            "mem_total_gb": round(total_mem, 1),
            "mem_used_gb": round(used_mem, 1),
            "mem_percent": round(used_mem / total_mem * 100, 1),
            "disk_used": disk_used,
            "disk_total": disk_total,
            "disk_percent": disk_percent,
        }
    except Exception as e:
        return {"error": str(e)}


def send_telegram_message(message: str) -> bool:
    """Envia mensagem via Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        return r.status_code == 200
    except:
        return False


# ================== SIDEBAR ==================
with st.sidebar:
    st.markdown("## 🖥️ Home Lab")
    st.markdown(f"**Servidor:** `{SERVER_IP}`")
    st.markdown("**Usuário:** `homelab`")
    st.markdown("---")

    # Status rápido
    st.markdown("### ⚡ Status Rápido")

    ollama_ok = check_service(f"{OLLAMA_URL}/api/tags")
    waha_ok = check_service(f"{WAHA_URL}/api/health")
    webui_ok = check_service(OPENWEBUI_URL)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"🦙 {'🟢' if ollama_ok else '🔴'}")
    with col2:
        st.markdown(f"💬 {'🟢' if waha_ok else '🔴'}")
    with col3:
        st.markdown(f"🌐 {'🟢' if webui_ok else '🔴'}")

    st.markdown("---")

    # Navegação
    st.markdown("### 📍 Navegação")
    page = st.radio(
        "Selecione:",
        [
            "🏠 Visão Geral",
            "🔧 Serviços",
            "🦙 Modelos Ollama",
            "⚙️ Configurações",
            "📊 Monitoramento",
            "🔗 Integrações",
        ],
        label_visibility="collapsed",
    )

# ================== PÁGINA PRINCIPAL ==================
st.markdown(
    '<h1 class="main-header">🖥️ Home Lab Control Panel</h1>', unsafe_allow_html=True
)

if page == "🏠 Visão Geral":
    st.markdown("## 📊 Visão Geral do Sistema")

    # Métricas do Sistema
    stats = get_system_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🖥️ CPU Load", stats.get("cpu_load", ["?"])[0])
    with col2:
        st.metric(
            "💾 RAM",
            f"{stats.get('mem_used_gb', '?')}/{stats.get('mem_total_gb', '?')} GB",
        )
    with col3:
        st.metric("💿 Disco", stats.get("disk_percent", "?"))
    with col4:
        models = get_ollama_models()
        st.metric("🦙 Modelos", len(models))

    st.markdown("---")

    # Status dos Serviços Principais
    st.markdown("### 🚀 Serviços Principais")

    services_to_check = [
        ("Ollama", "ollama", f"{OLLAMA_URL}/api/tags"),
        ("Open WebUI", "open-webui", OPENWEBUI_URL),
        ("WAHA WhatsApp", "waha", f"{WAHA_URL}/api/health"),
        ("Telegram Bot", "eddie-telegram-bot", None),
        ("WhatsApp Bot", "eddie-whatsapp-bot", None),
        ("Calendar", "eddie-calendar", None),
    ]

    cols = st.columns(3)
    for i, (name, systemd, url) in enumerate(services_to_check):
        with cols[i % 3]:
            status = check_systemd_service(systemd)
            is_online = status.get("active", False)

            if url:
                http_ok = check_service(url)
                icon = (
                    "🟢" if (is_online and http_ok) else ("🟡" if is_online else "🔴")
                )
            else:
                icon = "🟢" if is_online else "🔴"

            st.markdown(
                f"""
            <div class="service-card">
                <h4>{icon} {name}</h4>
                <small>Status: {status.get("state", "unknown")}</small>
            </div>
            """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Ações Rápidas
    st.markdown("### ⚡ Ações Rápidas")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Restart Telegram Bot", use_container_width=True):
            ok, msg = control_service("eddie-telegram-bot", "restart")
            st.success("✅ Reiniciado!" if ok else f"❌ Erro: {msg}")

    with col2:
        if st.button("🔄 Restart WhatsApp Bot", use_container_width=True):
            ok, msg = control_service("eddie-whatsapp-bot", "restart")
            st.success("✅ Reiniciado!" if ok else f"❌ Erro: {msg}")

    with col3:
        if st.button("📱 Testar Telegram", use_container_width=True):
            if send_telegram_message(
                "🖥️ *Teste do Dashboard*\n\n✅ Sistema funcionando!"
            ):
                st.success("✅ Mensagem enviada!")
            else:
                st.error("❌ Falha ao enviar")

    with col4:
        if st.button("🔄 Atualizar Tudo", use_container_width=True):
            st.rerun()

elif page == "🔧 Serviços":
    st.markdown("## 🔧 Gerenciamento de Serviços")

    # Lista de todos os serviços
    all_services = [
        ("eddie-telegram-bot", "Telegram Bot", "Bot para comandos via Telegram"),
        ("eddie-whatsapp-bot", "WhatsApp Bot", "Bot para comandos via WhatsApp"),
        ("eddie-calendar", "Calendar Service", "Lembretes do Google Calendar"),
        ("specialized-agents-api", "Agents API", "API de agentes especializados"),
        ("btc-trading-engine", "BTC Engine", "Engine de trading Bitcoin"),
        ("btc-webui-api", "BTC WebUI", "API para Open WebUI"),
        ("github-agent", "GitHub Agent", "Automação GitHub"),
        ("ollama", "Ollama", "Servidor de modelos LLM"),
        ("waha", "WAHA", "API WhatsApp"),
    ]

    for systemd, name, desc in all_services:
        status = check_systemd_service(systemd)
        is_active = status.get("active", False)

        with st.expander(
            f"{'🟢' if is_active else '🔴'} {name} - {desc}", expanded=False
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"""
                - **Serviço:** `{systemd}`
                - **Estado:** `{status.get("state", "unknown")}`
                - **SubEstado:** `{status.get("substate", "unknown")}`
                - **PID:** `{status.get("pid", "0")}`
                """)

            with col2:
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("▶️", key=f"start_{systemd}", help="Iniciar"):
                        ok, msg = control_service(systemd, "start")
                        st.toast("✅ Iniciado!" if ok else f"❌ {msg}")
                with c2:
                    if st.button("⏹️", key=f"stop_{systemd}", help="Parar"):
                        ok, msg = control_service(systemd, "stop")
                        st.toast("✅ Parado!" if ok else f"❌ {msg}")
                with c3:
                    if st.button("🔄", key=f"restart_{systemd}", help="Reiniciar"):
                        ok, msg = control_service(systemd, "restart")
                        st.toast("✅ Reiniciado!" if ok else f"❌ {msg}")

elif page == "🦙 Modelos Ollama":
    st.markdown("## 🦙 Modelos Ollama")

    models = get_ollama_models()

    if models:
        st.success(f"✅ {len(models)} modelos disponíveis")

        for model in models:
            name = model.get("name", "unknown")
            size = model.get("size", 0) / (1024**3)  # GB
            modified = model.get("modified_at", "")

            with st.expander(f"🦙 {name} ({size:.1f} GB)"):
                st.json(model)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Remover", key=f"rm_{name}"):
                        try:
                            r = requests.delete(
                                f"{OLLAMA_URL}/api/delete", json={"name": name}
                            )
                            st.success(
                                "✅ Removido!"
                                if r.status_code == 200
                                else f"❌ Erro: {r.text}"
                            )
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")
    else:
        st.warning("⚠️ Nenhum modelo encontrado ou Ollama offline")

    st.markdown("---")

    # Criar novo modelo
    st.markdown("### ➕ Criar Novo Modelo")

    model_name = st.text_input("Nome do modelo")
    modelfile = st.text_area(
        "Modelfile",
        height=200,
        placeholder="FROM codestral:22b\nSYSTEM Você é um assistente...",
    )

    if st.button("🚀 Criar Modelo", disabled=not model_name):
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/create",
                json={"name": model_name, "modelfile": modelfile},
                stream=True,
                timeout=300,
            )

            progress = st.progress(0)
            for line in r.iter_lines():
                if line:
                    data = json.loads(line)
                    status = data.get("status", "")
                    st.write(status)

            st.success(f"✅ Modelo {model_name} criado!")
        except Exception as e:
            st.error(f"❌ Erro: {e}")

elif page == "⚙️ Configurações":
    st.markdown("## ⚙️ Configurações do Sistema")

    tab1, tab2, tab3 = st.tabs(["🔑 Credenciais", "🌐 URLs & Portas", "📁 Arquivos"])

    with tab1:
        st.markdown("### 🔑 Credenciais Configuradas")

        st.markdown("""
        | Serviço | Variável | Status |
        |---------|----------|--------|
        | Telegram | `TELEGRAM_BOT_TOKEN` | ✅ Configurado |
        | Telegram | `TELEGRAM_CHAT_ID` | ✅ Configurado |
        | GitHub | `GITHUB_TOKEN` | ✅ Configurado |
        | WhatsApp | `WHATSAPP_NUMBER` | ✅ 5511981193899 |
        """)

        st.warning("⚠️ Credenciais são gerenciadas via `.env` no servidor")

    with tab2:
        st.markdown("### 🌐 URLs e Portas")

        ports_data = [
            ("Ollama API", SERVER_IP, 11434, f"{OLLAMA_URL}/api/tags"),
            ("Open WebUI", SERVER_IP, 3000, OPENWEBUI_URL),
            ("WAHA API", SERVER_IP, 3001, f"{WAHA_URL}/api/health"),
            ("WAHA Dashboard", SERVER_IP, 3001, f"{WAHA_URL}/dashboard"),
            ("Agents API", SERVER_IP, 8503, f"http://{SERVER_IP}:8503/health"),
            ("BTC WebUI", SERVER_IP, 8510, f"http://{SERVER_IP}:8510/health"),
            ("BTC Engine", SERVER_IP, 8511, f"http://{SERVER_IP}:8511/health"),
            ("Dashboard", SERVER_IP, 8500, f"http://{SERVER_IP}:8500"),
        ]

        for name, ip, port, url in ports_data:
            is_up = check_service(url) if url else False
            status = "🟢" if is_up else "🔴"
            st.markdown(f"- {status} **{name}**: `{ip}:{port}` - [Abrir]({url})")

    with tab3:
        st.markdown("### 📁 Arquivos de Configuração")

        config_files = [
            (".env", "Variáveis de ambiente"),
            ("dashboard/config.py", "Configuração centralizada"),
            ("mcp_ssh_config.json", "Configuração MCP SSH"),
            ("btc_trading_agent/config.json", "Config do trading"),
        ]

        for file, desc in config_files:
            filepath = Path(f"/home/homelab/myClaude/{file}")
            exists = filepath.exists() if not file.startswith("http") else True
            st.markdown(f"- {'✅' if exists else '❌'} `{file}` - {desc}")

elif page == "📊 Monitoramento":
    st.markdown("## 📊 Monitoramento do Sistema")

    # Auto-refresh
    auto_refresh = st.checkbox("🔄 Auto-refresh (10s)")

    stats = get_system_stats()

    # Métricas principais
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 🖥️ CPU")
        loads = stats.get("cpu_load", ["0", "0", "0"])
        st.metric("Load 1min", loads[0])
        st.metric("Load 5min", loads[1])
        st.metric("Load 15min", loads[2])

    with col2:
        st.markdown("### 💾 Memória")
        mem_percent = stats.get("mem_percent", 0)
        st.metric("Uso", f"{mem_percent}%")
        st.progress(mem_percent / 100)
        st.caption(f"{stats.get('mem_used_gb', 0)} / {stats.get('mem_total_gb', 0)} GB")

    with col3:
        st.markdown("### 💿 Disco")
        disk_pct = stats.get("disk_percent", "0%").replace("%", "")
        st.metric("Uso", stats.get("disk_percent", "?"))
        st.progress(int(disk_pct) / 100 if disk_pct.isdigit() else 0)
        st.caption(f"{stats.get('disk_used', '?')} / {stats.get('disk_total', '?')}")

    st.markdown("---")

    # Logs recentes
    st.markdown("### 📜 Logs Recentes")

    service_for_logs = st.selectbox(
        "Serviço",
        [
            "eddie-telegram-bot",
            "eddie-whatsapp-bot",
            "eddie-calendar",
            "ollama",
            "waha",
        ],
    )

    if st.button("📜 Ver Logs"):
        try:
            result = subprocess.run(
                ["journalctl", "-u", service_for_logs, "-n", "50", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            st.code(result.stdout, language="log")
        except Exception as e:
            st.error(f"Erro: {e}")

    if auto_refresh:
        import time

        time.sleep(10)
        st.rerun()

elif page == "🔗 Integrações":
    st.markdown("## 🔗 Integrações Externas")

    # Gmail
    with st.expander("📧 Gmail", expanded=True):
        gmail_token = Path("/home/homelab/myClaude/gmail_data/token.json")
        st.markdown(
            f"**Token:** {'✅ Configurado' if gmail_token.exists() else '❌ Não configurado'}"
        )
        st.markdown("**Funcionalidades:** Limpeza de emails, Expurgo automático")

    # Google Calendar
    with st.expander("📅 Google Calendar", expanded=True):
        cal_token = Path("/home/homelab/myClaude/calendar_data/token.json")
        st.markdown(
            f"**Token:** {'✅ Configurado' if cal_token.exists() else '❌ Não configurado'}"
        )
        st.markdown("**Funcionalidades:** Lembretes via Telegram/WhatsApp")

    # WhatsApp
    with st.expander("💬 WhatsApp (WAHA)", expanded=True):
        waha_status = check_service(f"{WAHA_URL}/api/health")
        st.markdown(f"**Status:** {'🟢 Online' if waha_status else '🔴 Offline'}")
        st.markdown(f"**Dashboard:** [{WAHA_URL}/dashboard]({WAHA_URL}/dashboard)")
        st.markdown("**Número:** 5511981193899")

    # GitHub
    with st.expander("🐙 GitHub", expanded=True):
        github_token = os.getenv("GITHUB_TOKEN", "")
        st.markdown(
            f"**Token:** {'✅ Configurado' if github_token else '❌ Não configurado'}"
        )
        st.markdown(
            "**Repo:** [eddiejdi/eddie-auto-dev](https://github.com/eddiejdi/eddie-auto-dev)"
        )

    # KuCoin
    with st.expander("💰 KuCoin Trading", expanded=True):
        kucoin_config = Path("/home/homelab/myClaude/btc_trading_agent/config.json")
        st.markdown(
            f"**Config:** {'✅ Existe' if kucoin_config.exists() else '❌ Não encontrado'}"
        )
        st.markdown("**Modo:** Simulação (dry-run)")

# ================== FOOTER ==================
st.markdown("---")
st.markdown(
    f"<center>🖥️ Home Lab Control Panel | "
    f"Servidor: {SERVER_IP} | "
    f"Atualizado: {datetime.now().strftime('%H:%M:%S')}</center>",
    unsafe_allow_html=True,
)
