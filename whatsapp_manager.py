#!/usr/bin/env python3
"""
Interface Web para Gerenciamento do WhatsApp Bot
Permite visualizar QR Code, status, enviar mensagens e ver logs

Acesse: http://localhost:5002
"""

import os
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

# Instalar: pip install streamlit httpx qrcode pillow

try:
    import streamlit as st
    import httpx
    import qrcode
    from io import BytesIO
    import base64
except ImportError:
    print("Instale as dependências:")
    print("pip install streamlit httpx qrcode pillow")
    exit(1)

# Configurações
WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:5001")
SESSION_NAME = "eddie"

# Configurar página
st.set_page_config(
    page_title="WhatsApp Bot Manager",
    page_icon="📱",
    layout="wide"
)

# CSS customizado
st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    font-weight: bold;
    color: #25D366;
    margin-bottom: 2rem;
}
.status-card {
    padding: 1.5rem;
    border-radius: 10px;
    margin-bottom: 1rem;
}
.status-connected {
    background-color: #d4edda;
    border-left: 5px solid #28a745;
}
.status-disconnected {
    background-color: #f8d7da;
    border-left: 5px solid #dc3545;
}
.status-pending {
    background-color: #fff3cd;
    border-left: 5px solid #ffc107;
}
.qr-container {
    display: flex;
    justify-content: center;
    padding: 2rem;
    background: white;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)


class WAHAManager:
    """Gerenciador do WAHA"""
    
    def __init__(self, base_url: str, session: str):
        self.base_url = base_url.rstrip("/")
        self.session = session
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Faz requisição síncrona"""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = getattr(client, method)(
                    f"{self.base_url}{endpoint}",
                    **kwargs
                )
                if response.status_code == 200:
                    return response.json()
                return {"error": f"Status {response.status_code}", "detail": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def get_status(self) -> dict:
        """Obtém status da sessão"""
        return self._request("get", f"/api/sessions/{self.session}")
    
    def start_session(self) -> dict:
        """Inicia sessão"""
        return self._request("post", "/api/sessions/start", json={"name": self.session})
    
    def stop_session(self) -> dict:
        """Para sessão"""
        return self._request("post", f"/api/sessions/{self.session}/stop")
    
    def restart_session(self) -> dict:
        """Reinicia sessão"""
        return self._request("post", f"/api/sessions/{self.session}/restart")
    
    def logout(self) -> dict:
        """Desconecta WhatsApp"""
        return self._request("post", f"/api/sessions/{self.session}/logout")
    
    def get_qr(self) -> Optional[str]:
        """Obtém QR Code"""
        try:
            with httpx.Client(timeout=30.0) as client:
                # Tentar endpoint de QR
                response = client.get(f"{self.base_url}/api/{self.session}/auth/qr")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("value", data.get("qr", None))
                
                # Tentar outro formato
                response = client.get(f"{self.base_url}/api/sessions/{self.session}/auth/qr")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("value", data.get("qr", None))
        except:
            pass
        return None
    
    def get_qr_image(self) -> Optional[bytes]:
        """Obtém QR Code como imagem"""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.base_url}/api/{self.session}/auth/qr",
                    headers={"Accept": "image/png"}
                )
                if response.status_code == 200 and "image" in response.headers.get("content-type", ""):
                    return response.content
        except:
            pass
        return None
    
    def send_message(self, number: str, text: str) -> dict:
        """Envia mensagem"""
        # Formatar número
        number = number.replace("+", "").replace("-", "").replace(" ", "")
        if not number.endswith("@s.whatsapp.net"):
            number = f"{number}@s.whatsapp.net"
        
        return self._request("post", "/api/sendText", json={
            "chatId": number,
            "text": text,
            "session": self.session
        })
    
    def get_chats(self) -> list:
        """Lista chats"""
        result = self._request("get", f"/api/{self.session}/chats")
        if isinstance(result, list):
            return result
        return result.get("chats", [])
    
    def get_me(self) -> dict:
        """Obtém informações do número conectado"""
        return self._request("get", f"/api/{self.session}/auth/me")


def main():
    """Função principal do Streamlit"""
    
    # Header
    st.markdown('<div class="main-header">📱 WhatsApp Bot Manager</div>', unsafe_allow_html=True)
    
    # Inicializar manager
    manager = WAHAManager(WAHA_URL, SESSION_NAME)
    
    # Sidebar com controles
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.text_input("WAHA URL", value=WAHA_URL, disabled=True)
        st.text_input("Sessão", value=SESSION_NAME, disabled=True)
        
        st.divider()
        
        st.header("🎮 Controles")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ Iniciar", use_container_width=True):
                result = manager.start_session()
                if "error" in result:
                    st.error(f"Erro: {result['error']}")
                else:
                    st.success("Sessão iniciada!")
                st.rerun()
        
        with col2:
            if st.button("⏹️ Parar", use_container_width=True):
                result = manager.stop_session()
                st.info("Sessão parada")
                st.rerun()
        
        col3, col4 = st.columns(2)
        with col3:
            if st.button("🔄 Reiniciar", use_container_width=True):
                result = manager.restart_session()
                st.info("Sessão reiniciada")
                st.rerun()
        
        with col4:
            if st.button("🚪 Logout", use_container_width=True):
                result = manager.logout()
                st.warning("Desconectado do WhatsApp")
                st.rerun()
        
        st.divider()
        
        if st.button("🔃 Atualizar Página", use_container_width=True):
            st.rerun()
    
    # Conteúdo principal
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Status", "📷 QR Code", "💬 Enviar Mensagem", "📋 Chats"])
    
    # Tab Status
    with tab1:
        st.header("Status da Conexão")
        
        status = manager.get_status()
        
        if "error" in status:
            st.markdown(f"""
            <div class="status-card status-disconnected">
                <h3>❌ Erro de Conexão</h3>
                <p>{status.get('error', 'Desconhecido')}</p>
                <p><small>Verifique se o WAHA está rodando em {WAHA_URL}</small></p>
            </div>
            """, unsafe_allow_html=True)
            
            st.code(f"docker logs waha", language="bash")
            
        else:
            session_status = status.get("status", status.get("state", "UNKNOWN"))
            
            status_class = "status-pending"
            status_icon = "🟡"
            
            if session_status in ["CONNECTED", "WORKING", "READY"]:
                status_class = "status-connected"
                status_icon = "🟢"
            elif session_status in ["FAILED", "STOPPED", "DISCONNECTED"]:
                status_class = "status-disconnected"
                status_icon = "🔴"
            
            st.markdown(f"""
            <div class="status-card {status_class}">
                <h3>{status_icon} Status: {session_status}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # Informações detalhadas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Sessão", SESSION_NAME)
            
            with col2:
                me = manager.get_me()
                number = me.get("id", me.get("wid", {}).get("user", "N/A"))
                st.metric("Número", number)
            
            with col3:
                engine = status.get("config", {}).get("engine", status.get("engine", "WEBJS"))
                st.metric("Engine", engine)
            
            # JSON completo
            with st.expander("📝 Dados Completos"):
                st.json(status)
    
    # Tab QR Code
    with tab2:
        st.header("QR Code para Conexão")
        
        status = manager.get_status()
        session_status = status.get("status", status.get("state", "UNKNOWN"))
        
        if session_status in ["CONNECTED", "WORKING", "READY"]:
            st.success("✅ WhatsApp já está conectado!")
            
            me = manager.get_me()
            if me and "error" not in me:
                st.info(f"Conectado como: {me.get('id', me.get('pushname', 'N/A'))}")
        
        elif session_status in ["SCAN_QR_CODE", "STARTING", "INITIALIZING"]:
            st.warning("📱 Escaneie o QR Code com seu WhatsApp:")
            
            # Tentar obter QR como imagem
            qr_image = manager.get_qr_image()
            
            if qr_image:
                st.image(qr_image, caption="QR Code do WhatsApp", width=300)
            else:
                # Tentar obter QR como texto e gerar imagem
                qr_text = manager.get_qr()
                
                if qr_text:
                    # Gerar QR Code
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(qr_text)
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # Converter para bytes
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    
                    st.image(buffer.getvalue(), caption="QR Code do WhatsApp", width=300)
                    
                    with st.expander("📝 QR Code (texto)"):
                        st.code(qr_text)
                else:
                    st.error("QR Code não disponível. Tente reiniciar a sessão.")
            
            st.info("Após escanear, clique em 'Atualizar Página' na sidebar")
        
        else:
            st.info(f"Status atual: {session_status}")
            st.warning("Clique em 'Iniciar' na sidebar para gerar o QR Code")
    
    # Tab Enviar Mensagem
    with tab3:
        st.header("Enviar Mensagem de Teste")
        
        status = manager.get_status()
        session_status = status.get("status", status.get("state", "UNKNOWN"))
        
        if session_status not in ["CONNECTED", "WORKING", "READY"]:
            st.warning("⚠️ WhatsApp não está conectado. Conecte primeiro na aba 'QR Code'")
        else:
            with st.form("send_message"):
                number = st.text_input(
                    "Número do WhatsApp",
                    value="5511981193899",
                    help="Formato: código do país + DDD + número (ex: 5511999999999)"
                )
                
                message = st.text_area(
                    "Mensagem",
                    value="Olá! Esta é uma mensagem de teste do Eddie WhatsApp Bot 🤖",
                    height=100
                )
                
                submitted = st.form_submit_button("📤 Enviar Mensagem", use_container_width=True)
                
                if submitted:
                    if number and message:
                        with st.spinner("Enviando..."):
                            result = manager.send_message(number, message)
                        
                        if "error" in result:
                            st.error(f"Erro ao enviar: {result['error']}")
                        else:
                            st.success("✅ Mensagem enviada com sucesso!")
                            st.json(result)
                    else:
                        st.warning("Preencha número e mensagem")
    
    # Tab Chats
    with tab4:
        st.header("Conversas Recentes")
        
        status = manager.get_status()
        session_status = status.get("status", status.get("state", "UNKNOWN"))
        
        if session_status not in ["CONNECTED", "WORKING", "READY"]:
            st.warning("⚠️ WhatsApp não está conectado")
        else:
            if st.button("🔄 Carregar Chats"):
                with st.spinner("Carregando..."):
                    chats = manager.get_chats()
                
                if chats:
                    for chat in chats[:20]:  # Limitar a 20
                        chat_id = chat.get("id", chat.get("chatId", ""))
                        name = chat.get("name", chat.get("pushname", chat_id))
                        
                        is_group = "@g.us" in str(chat_id)
                        icon = "👥" if is_group else "👤"
                        
                        with st.expander(f"{icon} {name}"):
                            st.code(chat_id)
                            st.json(chat)
                else:
                    st.info("Nenhum chat encontrado")
    
    # Footer
    st.divider()
    st.caption(f"WhatsApp Bot Manager | WAHA: {WAHA_URL} | Atualizado: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
