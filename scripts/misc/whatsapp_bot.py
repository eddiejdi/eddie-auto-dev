#!/usr/bin/env python3
"""
Bot WhatsApp Completo com Integração aos Agentes Especializados
Usa neonize (Baileys Python wrapper) para conexão com WhatsApp

Recursos:
- Conexão multi-device (WhatsApp Web)
- Integração com Ollama/OpenWebUI
- Auto-desenvolvimento de soluções
- Busca web integrada
- Histórico de conversas
- Suporte a grupos

Número configurado: 5511981193899
"""

import os
import asyncio
import httpx
import json
import re
import base64
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import sys
import threading
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

# Adicionar diretório atual ao path para imports locais
sys.path.insert(0, str(Path(__file__).parent))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/tmp/whatsapp_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('WhatsAppBot')

# Import do módulo de busca web
try:
    from web_search import WebSearchEngine, create_search_engine
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    logger.warning("Módulo web_search não encontrado - busca web desabilitada")

# Import do módulo de integração OpenWebUI + Modelos
try:
    from openwebui_integration import (
        IntegrationClient, get_integration_client, close_integration,
        MODEL_PROFILES, ChatResponse
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False
    logger.warning("Módulo openwebui_integration não encontrado")

# Import do módulo de Google Calendar
try:
    from google_calendar_integration import (
        get_calendar_assistant, process_calendar_request, CalendarAssistant
    )
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False
    logger.warning("Módulo google_calendar_integration não encontrado - calendário desabilitado")

# Import do módulo de Gmail
try:
    from gmail_integration import (
        get_gmail_client, get_email_cleaner, process_gmail_command
    )
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    logger.warning("Módulo gmail_integration não encontrado - Gmail desabilitado")

# Import do módulo de Relatórios
try:
    from reports_integration import (
        process_report_request, detect_report_type, generate_report,
        get_report_commands
    )
    REPORTS_AVAILABLE = True
except ImportError:
    REPORTS_AVAILABLE = False
    logger.warning("Módulo reports_integration não encontrado - relatórios desabilitados")

# Import do módulo de Home Assistant
try:
    from home_assistant_integration import (
        process_home_command, detect_home_intent, get_home_commands
    )
    HOME_AVAILABLE = True
except ImportError:
    HOME_AVAILABLE = False
    logger.warning("Módulo home_assistant_integration não encontrado - automação desabilitada")

# ============== Configurações ==
# Número do WhatsApp (formato: código do país + DDD + número, sem +)
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "5511981193899")
WHATSAPP_PHONE_ID = f"{WHATSAPP_NUMBER}@s.whatsapp.net"

# Configurações de IA
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
MODEL = os.getenv("OLLAMA_MODEL", "shared-coder")
OPENWEBUI_HOST = os.getenv("OPENWEBUI_HOST", "http://192.168.15.2:3000")
AGENTS_API = os.getenv("AGENTS_API", "http://localhost:8503")

# Admin - quem pode usar comandos avançados
ADMIN_NUMBERS = os.getenv("ADMIN_NUMBERS", "5511981193899").split(",")

# Número do dono (Edenilson) - acesso total ao modelo
OWNER_NUMBER = "5511981193899"

# Whitelist — quando OWNER_ONLY=true, apenas OWNER_NUMBER + ALLOWED_NUMBERS podem usar o bot
# Para liberar para todos, defina OWNER_ONLY=false
OWNER_ONLY = os.getenv("OWNER_ONLY", "true").lower() in ("true", "1", "yes")
ALLOWED_NUMBERS = [n.strip() for n in os.getenv("ALLOWED_NUMBERS", OWNER_NUMBER).split(",") if n.strip()]
if OWNER_NUMBER not in ALLOWED_NUMBERS:
    ALLOWED_NUMBERS.append(OWNER_NUMBER)

# Mapeamento de números específicos para modelos personalizados
# Formato: número (sem código do país) -> modelo
PHONE_MODEL_MAPPING = {
    "11981193899": "shared-homelab",
}

# Caminho dos dados
DATA_DIR = Path(__file__).parent / "whatsapp_data"
DATA_DIR.mkdir(exist_ok=True)

# Mapeamento de perfis para uso rápido
PROFILE_ALIASES = {
    "code": "coder", "dev": "coder", "programar": "coder",
    "home": "homelab", "server": "homelab", "infra": "homelab",
    "git": "github", "repo": "github",
    "rapido": "fast", "quick": "fast",
    "avancado": "advanced", "complex": "advanced",
    "deep": "deepseek",
    "pessoal": "assistant", "msg": "assistant", "mensagem": "assistant",
    "texto": "assistant", "amor": "assistant", "criativo": "assistant"
}

# Padrões que indicam que a IA não consegue responder
INABILITY_PATTERNS = [
    r"não (tenho|possuo|consigo|sei|posso)",
    r"não estou (preparado|configurado|equipado)",
    r"não é possível",
    r"desculpe.*(não|nao)",
    r"infelizmente.*(não|nao)",
    r"fora (do meu|das minhas)",
    r"além (do meu|das minhas)",
    r"não fui (treinado|programado)",
    r"limitações",
    r"não tenho (acesso|capacidade|habilidade)",
]


def _env_int(name: str, default: int) -> int:
    """Lê inteiro de env com fallback seguro."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


WHATSAPP_CONTEXT_SUMMARY_ENABLED = os.getenv(
    "WHATSAPP_CONTEXT_SUMMARY_ENABLED", "true"
).lower() in ("true", "1", "yes")
WHATSAPP_CONTEXT_RECENT_MESSAGES = max(4, _env_int("WHATSAPP_CONTEXT_RECENT_MESSAGES", 12))
WHATSAPP_CONTEXT_SUMMARY_TRIGGER = max(
    WHATSAPP_CONTEXT_RECENT_MESSAGES + 1,
    _env_int("WHATSAPP_CONTEXT_SUMMARY_TRIGGER", 16),
)
WHATSAPP_CONTEXT_SUMMARY_MAX_CHARS = max(300, _env_int("WHATSAPP_CONTEXT_SUMMARY_MAX_CHARS", 1200))
WHATSAPP_CONTEXT_SUMMARY_MODEL = os.getenv("WHATSAPP_CONTEXT_SUMMARY_MODEL", "").strip()


@dataclass
class WhatsAppMessage:
    """Representa uma mensagem do WhatsApp"""
    id: str
    chat_id: str
    sender: str
    text: str
    timestamp: datetime
    is_group: bool = False
    group_name: str = None
    quoted_message: str = None
    media_type: str = None
    media_url: str = None
    
    @property
    def is_from_me(self) -> bool:
        return self.sender == WHATSAPP_PHONE_ID


@dataclass
class ChatSession:
    """Sessão de chat com histórico"""
    chat_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    current_profile: str = "assistant"
    last_activity: datetime = field(default_factory=datetime.now)
    rolling_summary: str = ""
    pending_summary_messages: List[Dict[str, str]] = field(default_factory=list)

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.last_activity = datetime.now()
        if not WHATSAPP_CONTEXT_SUMMARY_ENABLED:
            if len(self.messages) > 20:
                self.messages = self.messages[-20:]
            return
        while len(self.messages) > WHATSAPP_CONTEXT_RECENT_MESSAGES:
            self.pending_summary_messages.append(self.messages.pop(0))

    def get_history(self) -> List[Dict[str, str]]:
        history: List[Dict[str, str]] = []
        if self.rolling_summary:
            history.append({
                "role": "system",
                "content": (
                    "Resumo acumulado da conversa ate aqui. "
                    "Use como contexto, sem repetir isso ao usuario:\n"
                    f"{self.rolling_summary}"
                ),
            })
        history.extend(self.pending_summary_messages)
        history.extend(self.messages)
        return history.copy()

    def needs_summary_refresh(self) -> bool:
        """Indica quando já vale compactar histórico em resumo."""
        return (
            WHATSAPP_CONTEXT_SUMMARY_ENABLED
            and len(self.pending_summary_messages) >= 2
            and (
                len(self.pending_summary_messages) >= 6
                or (len(self.pending_summary_messages) + len(self.messages)) >= WHATSAPP_CONTEXT_SUMMARY_TRIGGER
            )
        )

    def build_summary_prompt(self) -> Optional[str]:
        """Monta prompt incremental para consolidar histórico antigo."""
        if not self.pending_summary_messages:
            return None
        previous_summary = self.rolling_summary.strip() or "Sem resumo anterior."
        chunk_lines = []
        for message in self.pending_summary_messages:
            role = message.get("role", "user")
            content = message.get("content", "").strip()
            if content:
                chunk_lines.append(f"{role}: {content}")
        if not chunk_lines:
            return None
        chunk_text = "\n".join(chunk_lines)
        return f"""Atualize o resumo cumulativo da conversa em portugues.

Resumo anterior:
{previous_summary}

Novas mensagens a incorporar:
{chunk_text}

Produza um resumo curto, factual e util para contexto futuro.
Inclua apenas preferencias, pendencias, decisoes, fatos e contexto duradouro.
Nao inclua cumprimento, enchimento ou texto ao usuario.
Limite maximo: {WHATSAPP_CONTEXT_SUMMARY_MAX_CHARS} caracteres."""

    def apply_summary(self, summary: str):
        """Aplica resumo consolidado e limpa backlog compactado."""
        normalized = " ".join(summary.split()).strip()
        self.rolling_summary = normalized[:WHATSAPP_CONTEXT_SUMMARY_MAX_CHARS]
        self.pending_summary_messages = []
        self.last_activity = datetime.now()

    def clear(self):
        self.messages = []
        self.rolling_summary = ""
        self.pending_summary_messages = []


class ConversationDB:
    """Banco de dados para conversas (PostgreSQL)"""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = os.getenv("DATABASE_URL", "postgresql://postgress:shared_memory_2026@localhost:5432/estou_aqui")
        
        self.database_url = database_url
        self.available = False
        # Connection pool para melhor performance
        try:
            self.pool = SimpleConnectionPool(1, 10, database_url)
            logger.info("✓ Pool de conexões PostgreSQL criado com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao criar pool PostgreSQL: {e}")
            raise
        
        self.init_db()
        self.available = True
    
    def get_connection(self):
        """Obtém conexão do pool"""
        return self.pool.getconn()
    
    def release_connection(self, conn):
        """Devolve conexão ao pool"""
        self.pool.putconn(conn)
    
    def init_db(self):
        """Inicializa o banco de dados PostgreSQL"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Criar schema para WhatsApp se não existir
            cursor.execute('''
                CREATE SCHEMA IF NOT EXISTS whatsapp
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS whatsapp.messages (
                    id SERIAL PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_group BOOLEAN DEFAULT FALSE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS whatsapp.sessions (
                    chat_id TEXT PRIMARY KEY,
                    profile TEXT DEFAULT 'assistant',
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_chat 
                ON whatsapp.messages(chat_id, timestamp DESC)
            ''')
            
            conn.commit()
            logger.info("✓ Schema PostgreSQL do WhatsApp inicializado")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar DB: {e}")
            conn.rollback()
            raise
        finally:
            self.release_connection(conn)
    
    def save_message(self, chat_id: str, sender: str, role: str, 
                     content: str, is_group: bool = False):
        """Salva mensagem no banco"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO whatsapp.messages (chat_id, sender, role, content, is_group)
                VALUES (%s, %s, %s, %s, %s)
            ''', (chat_id, sender, role, content, is_group))
            conn.commit()
        except Exception as e:
            logger.error(f"❌ Erro ao salvar mensagem: {e}")
            conn.rollback()
        finally:
            self.release_connection(conn)
    
    def get_history(self, chat_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """Recupera histórico de mensagens"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT role, content FROM whatsapp.messages 
                WHERE chat_id = %s 
                ORDER BY timestamp DESC LIMIT %s
            ''', (chat_id, limit))
            rows = cursor.fetchall()
            # Reverter para ordem cronológica
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
        finally:
            self.release_connection(conn)
    
    def get_session_profile(self, chat_id: str) -> str:
        """Obtém perfil da sessão"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT profile FROM whatsapp.sessions WHERE chat_id = %s', (chat_id,))
            row = cursor.fetchone()
            return row[0] if row else "assistant"
        finally:
            self.release_connection(conn)
    
    def set_session_profile(self, chat_id: str, profile: str):
        """Define perfil da sessão"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO whatsapp.sessions (chat_id, profile, last_activity)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (chat_id) DO UPDATE 
                SET profile = EXCLUDED.profile, last_activity = CURRENT_TIMESTAMP
            ''', (chat_id, profile))
            conn.commit()
        except Exception as e:
            logger.error(f"❌ Erro ao definir perfil: {e}")
            conn.rollback()
        finally:
            self.release_connection(conn)
    
    def clear_history(self, chat_id: str):
        """Limpa histórico de um chat"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM whatsapp.messages WHERE chat_id = %s', (chat_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"❌ Erro ao limpar histórico: {e}")
            conn.rollback()
        finally:
            self.release_connection(conn)


class NullConversationDB:
    """Fallback em memória quando o banco não está disponível."""

    available = False

    def get_history(self, chat_id: str, limit: int = 20) -> List[Dict[str, str]]:
        return []

    def get_session_profile(self, chat_id: str) -> str:
        return "assistant"

    def set_session_profile(self, chat_id: str, profile: str):
        return None

    def clear_history(self, chat_id: str):
        return None

    def save_message(self, chat_id: str, sender: str, role: str,
                     content: str, is_group: bool = False):
        return None


class OllamaClient:
    """Cliente para comunicação com Ollama"""
    
    def __init__(self, host: str = OLLAMA_HOST):
        self.host = host
        self.client = httpx.AsyncClient(timeout=120.0)

    @staticmethod
    def _normalize_validator_result(result: Any) -> Tuple[bool, str]:
        """Normaliza retorno do validator para ok/reason."""
        if isinstance(result, tuple):
            ok = bool(result[0])
            reason = str(result[1]).strip() if len(result) > 1 and result[1] is not None else ""
            return ok, reason
        return bool(result), ""

    @staticmethod
    def _default_text_validator(text: str) -> Tuple[bool, str]:
        """Rejeita saídas vazias ou mensagens de erro da camada HTTP."""
        normalized = (text or "").strip()
        if not normalized:
            return False, "resposta vazia"
        if normalized.startswith("Erro"):
            return False, normalized[:120]
        return True, ""

    @staticmethod
    def _build_retry_message(reason: str) -> Dict[str, str]:
        """Instrução curta para o modelo corrigir a resposta no retry."""
        return {
            "role": "system",
            "content": (
                "Sua resposta anterior falhou na validacao interna. "
                f"Motivo: {reason or 'saida invalida'}. "
                "Refaca a resposta final do zero, mantendo o contexto e respondendo diretamente ao usuario."
            ),
        }
    
    async def chat(self, messages: List[Dict[str, str]], model: str = MODEL,
                   system: str = None) -> str:
        """Envia mensagem para o modelo"""
        try:
            full_messages = []
            
            if system:
                full_messages.append({"role": "system", "content": system})
            
            full_messages.extend(messages)
            
            response = await self.client.post(
                f"{self.host}/api/chat",
                json={
                    "model": model,
                    "messages": full_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2048
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "Erro ao processar resposta")
            else:
                logger.error(f"Erro Ollama: {response.status_code} - {response.text}")
                return f"Erro ao conectar com modelo: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Exceção no Ollama: {e}")
            return f"Erro de conexão: {str(e)}"

    async def chat_validated(
        self,
        messages: List[Dict[str, str]],
        model: str = MODEL,
        system: str = None,
        validator=None,
        max_attempts: int = 2,
    ) -> str:
        """Executa chat com validação simples e um retry orientado."""
        validation = validator or self._default_text_validator
        current_messages = [msg.copy() for msg in messages]
        last_response = ""
        last_reason = "resposta vazia"

        for attempt in range(1, max_attempts + 1):
            response = await self.chat(current_messages, model, system)
            last_response = response
            ok, reason = self._normalize_validator_result(validation(response))
            if ok:
                return response
            last_reason = reason or "resposta rejeitada pela validacao"
            if attempt < max_attempts:
                current_messages.append(self._build_retry_message(last_reason))

        return last_response

    async def generate(self, prompt: str, model: str = MODEL, system: str = None) -> str:
        """Gera texto simples"""
        try:
            data = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7}
            }
            if system:
                data["system"] = system
            
            response = await self.client.post(f"{self.host}/api/generate", json=data)
            
            if response.status_code == 200:
                return response.json().get("response", "")
            return f"Erro: {response.status_code}"
            
        except Exception as e:
            return f"Erro: {str(e)}"

    async def generate_validated(
        self,
        prompt: str,
        model: str = MODEL,
        system: str = None,
        validator=None,
        max_attempts: int = 2,
    ) -> str:
        """Executa generate com validação explícita e um retry de reparo."""
        validation = validator or self._default_text_validator
        current_prompt = prompt
        last_response = ""
        last_reason = "resposta vazia"

        for attempt in range(1, max_attempts + 1):
            response = await self.generate(current_prompt, model, system)
            last_response = response
            ok, reason = self._normalize_validator_result(validation(response))
            if ok:
                return response
            last_reason = reason or "resposta rejeitada pela validacao"
            if attempt < max_attempts:
                current_prompt = (
                    f"{prompt}\n\n"
                    "A saida anterior falhou na validacao.\n"
                    f"Motivo: {last_reason}\n\n"
                    f"Saida anterior:\n{response or '(vazio)'}\n\n"
                    "Rescreva a resposta final corrigida, sem texto adicional."
                )

        return last_response

    async def list_models(self) -> List[str]:
        """Lista modelos disponíveis"""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m.get("name", "") for m in models]
            return []
        except:
            return []
    
    async def close(self):
        await self.client.aclose()


class WhatsAppBot:
    """Bot principal do WhatsApp"""
    
    def __init__(self):
        try:
            self.db = ConversationDB()
        except Exception as e:
            logger.error(f"DB indisponível, usando fallback em memória: {e}")
            self.db = NullConversationDB()
        self.ollama = OllamaClient()
        self.sessions: Dict[str, ChatSession] = {}
        self.search_engine = None
        self.running = False
        self.whatsapp_client = None
        
        # Inicializar busca web se disponível
        if WEB_SEARCH_AVAILABLE:
            try:
                self.search_engine = create_search_engine()
                logger.info("Motor de busca web inicializado")
            except Exception as e:
                logger.error(f"Erro ao inicializar busca: {e}")
    
    def get_session(self, chat_id: str) -> ChatSession:
        """Obtém ou cria sessão de chat"""
        if chat_id not in self.sessions:
            # Carregar histórico do banco
            history = self.db.get_history(chat_id)
            profile = self.db.get_session_profile(chat_id)
            
            session = ChatSession(
                chat_id=chat_id,
                messages=history,
                current_profile=profile
            )
            self.sessions[chat_id] = session
        
        return self.sessions[chat_id]

    @staticmethod
    def _response_validator(text: str) -> Tuple[bool, str]:
        """Aceita respostas úteis e rejeita saídas vazias/erro."""
        normalized = (text or "").strip()
        if not normalized:
            return False, "resposta vazia"
        if normalized.startswith("Erro"):
            return False, normalized[:120]
        return True, ""

    async def refresh_session_summary(self, session: ChatSession, model: str):
        """Compacta histórico antigo em um resumo cumulativo antes da próxima chamada."""
        if not session.needs_summary_refresh():
            return
        prompt = session.build_summary_prompt()
        if not prompt:
            return
        summary_model = WHATSAPP_CONTEXT_SUMMARY_MODEL or model
        summary = await self.ollama.generate_validated(
            prompt,
            model=summary_model,
            validator=lambda text: (
                bool(text.strip()) and not text.strip().startswith("Erro"),
                "resumo vazio ou invalido",
            ),
            max_attempts=2,
        )
        normalized = summary.strip()
        if not normalized or normalized.startswith("Erro"):
            logger.warning(
                "Falha ao atualizar resumo da sessao %s: %s",
                session.chat_id,
                normalized[:160] if normalized else "vazio",
            )
            return
        session.apply_summary(normalized)
        logger.info(
            "Resumo incremental atualizado para %s (%s chars)",
            session.chat_id,
            len(session.rolling_summary),
        )
    
    def is_admin(self, sender: str) -> bool:
        """Verifica se o remetente é admin"""
        # Extrair número do JID
        number = sender.split("@")[0]
        return number in ADMIN_NUMBERS or sender in ADMIN_NUMBERS
    
    async def handle_command(self, message: WhatsAppMessage) -> Optional[str]:
        """Processa comandos especiais"""
        text = message.text.strip().lower()
        
        # Comandos básicos
        if text in ["/start", "/help", "ajuda", "menu"]:
            return self.get_help_text(message.is_group)
        
        if text in ["/ping", "ping"]:
            return "🏓 Pong! Bot WhatsApp online e funcionando!"
        
        if text in ["/limpar", "/clear", "limpar historico"]:
            self.db.clear_history(message.chat_id)
            if message.chat_id in self.sessions:
                self.sessions[message.chat_id].clear()
            return "🧹 Histórico limpo! Nova conversa iniciada."
        
        if text.startswith("/perfil ") or text.startswith("perfil "):
            profile = text.split(" ", 1)[1].strip()
            profile = PROFILE_ALIASES.get(profile, profile)
            
            session = self.get_session(message.chat_id)
            session.current_profile = profile
            self.db.set_session_profile(message.chat_id, profile)
            
            return f"✅ Perfil alterado para: *{profile}*\n\nPerfis disponíveis: coder, homelab, github, assistant, fast, advanced"
        
        if text in ["/modelos", "/models", "modelos"]:
            models = await self.ollama.list_models()
            if models:
                return "📋 *Modelos disponíveis:*\n" + "\n".join([f"• {m}" for m in models[:15]])
            return "❌ Erro ao listar modelos"
        
        if text in ["/status", "status"]:
            session = self.get_session(message.chat_id)
            calendar_status = "✅" if CALENDAR_AVAILABLE else "❌"
            gmail_status = "✅" if GMAIL_AVAILABLE else "❌"
            home_status = "✅" if HOME_AVAILABLE else "❌"
            return f"""📊 *Status do Bot*

🔢 Número: {WHATSAPP_NUMBER}
🤖 Modelo: {MODEL}
👤 Perfil atual: {session.current_profile}
💬 Mensagens na sessão: {len(session.messages)}
🧠 Resumo ativo: {'✅' if session.rolling_summary else '❌'}
🔍 Busca web: {'✅' if self.search_engine else '❌'}
🧠 Integração IA: {'✅' if INTEGRATION_AVAILABLE else '❌'}
📅 Google Calendar: {calendar_status}
📧 Gmail: {gmail_status}
🏠 Casa Inteligente: {home_status}"""
        
        # === Comandos de Gmail ===
        if text.startswith("/gmail") or text.startswith("/email"):
            if not GMAIL_AVAILABLE:
                return ("⚠️ *Gmail não disponível*\n\n"
                       "O módulo de Gmail não está instalado.\n"
                       "Execute: `pip install google-auth-oauthlib google-api-python-client`")
            
            # Extrair comando e argumentos
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                gmail_text = parts[1]
                gmail_parts = gmail_text.split(maxsplit=1)
                gmail_cmd = gmail_parts[0] if gmail_parts else "ajuda"
                gmail_args = gmail_parts[1] if len(gmail_parts) > 1 else ""
            else:
                gmail_cmd = "ajuda"
                gmail_args = ""
            
            return await process_gmail_command(gmail_cmd, gmail_args)
        
        # === Comandos de Calendário ===
        if text.startswith("/calendar") or text.startswith("/calendario") or text.startswith("/agenda"):
            if not CALENDAR_AVAILABLE:
                return ("⚠️ *Google Calendar não disponível*\n\n"
                       "O módulo de calendário não está instalado.\n"
                       "Execute: `pip install google-auth-oauthlib google-api-python-client python-dateutil`\n\n"
                       "Depois: `python setup_google_calendar.py`")
            
            # Processar comando do calendário
            calendar_assistant = get_calendar_assistant()
            
            # Extrair comando e argumentos
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                cal_text = parts[1]
                cal_parts = cal_text.split(maxsplit=1)
                cal_cmd = cal_parts[0] if cal_parts else "ajuda"
                cal_args = cal_parts[1] if len(cal_parts) > 1 else ""
            else:
                cal_cmd = "ajuda"
                cal_args = ""
            
            return await calendar_assistant.process_command(cal_cmd, cal_args, message.chat_id)
        
        # Comandos de admin
        if self.is_admin(message.sender):
            if text.startswith("/modelo ") or text.startswith("modelo "):
                new_model = text.split(" ", 1)[1].strip()
                return f"✅ Modelo alterado para: *{new_model}* (nota: alteração temporária, use /perfil para mudar perfil)"
            
            if text in ["/stats", "estatisticas"]:
                return await self.get_stats()
        
        # === Comandos de Casa/Home Assistant ===
        if text.startswith("/casa") or text.startswith("/home "):
            if not HOME_AVAILABLE:
                return ("⚠️ *Home Assistant não disponível*\n\n"
                       "O módulo de automação residencial não está instalado.")
            parts = text.split(maxsplit=1)
            home_text = parts[1] if len(parts) > 1 else "status"
            return await process_home_command(home_text, message.chat_id)

        # === Comandos de Relatório ===
        if text.startswith("/relatorio") or text.startswith("/report"):
            if not REPORTS_AVAILABLE:
                return "⚠️ *Módulo de relatórios não disponível*"
            
            # Extrair tipo de relatório
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                report_type = parts[1].strip()
            else:
                # Menu de relatórios
                return """📊 *Relatórios Disponíveis*

Use: /relatorio <tipo>

*Tipos disponíveis:*
• *btc* - Relatório do agente de trading Bitcoin
• *sistema* - Status dos serviços do servidor
• *homelab* - Visão geral da infraestrutura

*Exemplos:*
• `/relatorio btc`
• `/relatorio sistema`
• `/relatorio homelab`

💡 Você também pode pedir naturalmente:
• "como está o btc?"
• "status do sistema"
• "relatório de trading"
"""
            
            report = await process_report_request(report_type)
            if report:
                return report
            return f"❓ Tipo de relatório não reconhecido: {report_type}"

        return None

    def get_help_text(self, is_group: bool = False) -> str:
        """Retorna texto de ajuda"""
        group_note = "\n\n📌 *Em grupos:* Me mencione ou responda minhas mensagens!" if is_group else ""
        calendar_note = "\n\n📅 *Google Calendar:*\n• /calendar - Ajuda do calendário\n• /calendar listar - Ver eventos\n• /calendar criar [evento] - Agendar" if CALENDAR_AVAILABLE else ""       
        gmail_note = "\n\n📧 *Gmail:*\n• /gmail - Ajuda do Gmail\n• /gmail listar - Ver emails\n• /gmail analisar - Relatório\n• /gmail limpar - Limpar spam/promoções" if GMAIL_AVAILABLE else ""
        reports_note = "\n\n📊 *Relatórios:*\n• /relatorio - Menu de relatórios\n• /relatorio btc - Trading Bitcoin\n• /relatorio sistema - Status servidor" if REPORTS_AVAILABLE else ""
        home_note = "\n\n🏠 *Casa Inteligente:*\n• /casa status - Status dos dispositivos\n• /casa dispositivos - Listar dispositivos\n• _ligar ventilador_ - Comandos por voz\n• _desligar luz da sala_ - Controle natural" if HOME_AVAILABLE else ""

        return f"""🤖 *Shared WhatsApp Bot*

Olá! Sou um assistente de IA integrado ao WhatsApp.

*Comandos disponíveis:*

📝 *Conversa*
• Envie qualquer mensagem para conversar
• /limpar - Limpa histórico da conversa
• /perfil <nome> - Muda perfil (coder, homelab, assistant, etc)

🔧 *Informações*
• /status - Status do bot
• /modelos - Lista modelos disponíveis
• /ping - Verifica se estou online{calendar_note}{gmail_note}{reports_note}{home_note}

*Perfis disponíveis:*
• *coder* - Programação e código
• *homelab* - Servidores e infraestrutura
• *assistant* - Assistente geral
• *fast* - Respostas rápidas
• *advanced* - Análises complexas{group_note}

💡 *Dica:* Posso buscar na web, agendar eventos, gerenciar emails, gerar relatórios e usar IA para te ajudar!"""

    async def get_stats(self) -> str:
        """Retorna estatísticas (admin only)"""
        try:
            if not getattr(self.db, "available", True):
                return "❌ Estatísticas indisponíveis: banco de dados offline"
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM messages')
            total_msgs = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT chat_id) FROM messages')
            total_chats = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM messages 
                WHERE timestamp > datetime('now', '-24 hours')
            ''')
            msgs_24h = cursor.fetchone()[0]
            
            conn.close()
            
            return f"""📈 *Estatísticas do Bot*

📊 Total de mensagens: {total_msgs}
👥 Total de conversas: {total_chats}
📝 Mensagens (24h): {msgs_24h}
🔄 Sessões ativas: {len(self.sessions)}"""
            
        except Exception as e:
            return f"❌ Erro ao obter estatísticas: {e}"
    
    def detect_inability(self, response: str) -> bool:
        """Detecta se a IA não conseguiu responder"""
        response_lower = response.lower()
        for pattern in INABILITY_PATTERNS:
            if re.search(pattern, response_lower):
                return True
        return False
    
    async def web_search(self, query: str, max_results: int = 3) -> str:
        """Realiza busca web"""
        if not self.search_engine:
            return ""
        
        try:
            results = await self.search_engine.search(query, max_results)
            if results:
                context = "📚 *Informações encontradas na web:*\n\n"
                for i, r in enumerate(results, 1):
                    context += f"{i}. *{r.get('title', 'Sem título')}*\n"
                    context += f"   {r.get('snippet', '')}\n\n"
                return context
        except Exception as e:
            logger.error(f"Erro na busca web: {e}")
        
        return ""
    
    def is_owner(self, sender: str) -> bool:
        """Verifica se o remetente é o dono (Edenilson)"""
        # Extrair número do JID
        number = sender.split("@")[0]
        # Remover código do país se tiver
        clean_number = number.replace("55", "", 1) if number.startswith("55") else number
        owner_clean = OWNER_NUMBER.replace("55", "", 1) if OWNER_NUMBER.startswith("55") else OWNER_NUMBER
        return clean_number == owner_clean or number == OWNER_NUMBER or number == owner_clean
    
    async def process_message(self, message: WhatsAppMessage) -> str:
        """Processa uma mensagem e gera resposta"""
        # Ignorar mensagens próprias, EXCETO se for mensagem para si mesmo (Notes to Self)
        # Quando você envia mensagem para si mesmo, o chat_id é igual ao seu próprio número
        is_self_chat = message.chat_id == WHATSAPP_PHONE_ID or message.chat_id == f"{WHATSAPP_NUMBER}@c.us"
        
        if message.is_from_me and not is_self_chat:
            return None
        
        # Ignorar mensagens de grupo por padrão (exceto se mencionado)
        if message.is_group:
            # Só responde em grupos se for mencionado ou se for mensagem direta do admin
            if not self.is_admin(message.sender):
                logger.debug(f"Ignorando mensagem de grupo: {message.chat_id}")
                return None
        
        # Verificar se é comando
        command_response = await self.handle_command(message)
        if command_response:
            return command_response
        
        # === VERIFICAR INTENÇÃO DE CALENDÁRIO ===
        if CALENDAR_AVAILABLE:
            calendar_response = await process_calendar_request(message.text, message.chat_id)
            if calendar_response:
                logger.info(f"[Calendar] Detectada intenção de calendário: {message.text[:50]}...")
                return calendar_response
        
        # === VERIFICAR INTENÇÃO DE EMAIL/GMAIL ===
        if GMAIL_AVAILABLE:
            email_keywords = [
                'email', 'e-mail', 'gmail', 'inbox', 'caixa de entrada',
                'meus emails', 'ver emails', 'listar emails', 'ler emails',
                'limpar emails', 'spam', 'não lidos', 'nao lidos'
            ]
            text_lower = message.text.lower()
            if any(kw in text_lower for kw in email_keywords):
                logger.info(f"[Gmail] Detectada intenção de email: {message.text[:50]}...")
                
                # Mapear intenção para comando
                if 'limpar' in text_lower or 'excluir' in text_lower or 'deletar' in text_lower:
                    return await process_gmail_command('limpar', '')
                elif 'analisar' in text_lower or 'relatório' in text_lower or 'relatorio' in text_lower:
                    return await process_gmail_command('analisar', '')
                elif 'não lido' in text_lower or 'nao lido' in text_lower:
                    return await process_gmail_command('nao_lidos', '')
                else:
                    return await process_gmail_command('listar', '20')
        
        # === VERIFICAR INTENÇÃO DE AUTOMAÇÃO RESIDENCIAL ===
        if HOME_AVAILABLE:
            if detect_home_intent(message.text):
                logger.info(f"[HomeAssistant] Detectada intenção de automação: {message.text[:50]}...")
                home_response = await process_home_command(message.text, message.chat_id)
                if home_response:
                    return home_response

        # === VERIFICAR INTENÇÃO DE RELATÓRIO ===
        if REPORTS_AVAILABLE:
            text_lower = message.text.lower()
            report_keywords = [
                'relatório', 'relatorio', 'report', 'status',
                'como está o btc', 'como esta o btc', 'como está o bitcoin', 'como esta o bitcoin',
                'trading', 'status trading', 'status do sistema', 'status sistema',
                'homelab', 'como estão os servidores', 'como estao os servidores'
            ]
            if any(kw in text_lower for kw in report_keywords):
                logger.info(f"[Reports] Detectada intenção de relatório: {message.text[:50]}...")
                report = await process_report_request(message.text)
                if report:
                    return report
        
        # Obter sessão
        session = self.get_session(message.chat_id)
        
        # Salvar mensagem do usuário
        self.db.save_message(
            message.chat_id,
            message.sender,
            "user",
            message.text,
            message.is_group
        )
        session.add_message("user", message.text)
        
        # Verificar se é o dono (Edenilson) - acesso total
        is_owner = self.is_owner(message.sender)
        
        # Extrair número limpo do remetente
        sender_number = message.sender.split("@")[0]
        sender_clean = sender_number.replace("55", "", 1) if sender_number.startswith("55") else sender_number
        
        # Verificar se há modelo específico para este número
        if sender_clean in PHONE_MODEL_MAPPING:
            model = PHONE_MODEL_MAPPING[sender_clean]
            logger.info(f"📱 Número {sender_clean} mapeado para modelo específico: {model}")
        elif is_owner:
            # Dono tem acesso total ao shared-assistant
            model = "shared-assistant"
            logger.info(f"👤 Mensagem do DONO - usando modelo completo: {model}")
        else:
            # Outros recebem resposta como se fosse o Edenilson usando modelo treinado
            model = "shared-whatsapp"
            logger.info(f"📱 Mensagem de TERCEIRO ({message.sender}) - respondendo como Edenilson com modelo treinado")
        
        system_prompt = self.get_system_prompt(session.current_profile, is_owner)

        await self.refresh_session_summary(session, model)
        
        # Preparar mensagens para o modelo
        messages = session.get_history()
        
        # Primeira tentativa de resposta
        response = await self.ollama.chat_validated(
            messages,
            model,
            system_prompt,
            validator=self._response_validator,
            max_attempts=2,
        )
        
        # Se detectar incapacidade, tentar com busca web
        if self.detect_inability(response) and self.search_engine:
            logger.info(f"Incapacidade detectada, buscando na web: {message.text}")
            
            web_context = await self.web_search(message.text)
            if web_context:
                # Adicionar contexto da web
                enhanced_messages = messages.copy()
                enhanced_messages.append({
                    "role": "system",
                    "content": f"Use as seguintes informações para responder:\n{web_context}"
                })
                
                response = await self.ollama.chat_validated(
                    enhanced_messages,
                    model,
                    system_prompt,
                    validator=self._response_validator,
                    max_attempts=2,
                )
        
        # Salvar resposta
        self.db.save_message(
            message.chat_id,
            WHATSAPP_PHONE_ID,
            "assistant",
            response,
            message.is_group
        )
        session.add_message("assistant", response)
        
        return response
    
    def get_system_prompt(self, profile: str, is_owner: bool = True) -> str:
        """Retorna system prompt baseado no perfil e se é o dono"""
        
        # Se NÃO for o dono (Edenilson), responde como se fosse ele
        if not is_owner:
            return """Você é Edenilson (Shared), um especialista em tecnologia, programação e infraestrutura.
Responda como se fosse o próprio Edenilson falando com a pessoa.
Seja amigável, prestativo e natural nas respostas.
Você trabalha com:
- Desenvolvimento de software (Python, JavaScript, etc)
- DevOps e infraestrutura (Docker, Kubernetes, Linux)
- Inteligência Artificial e automação
- Homelab e servidores

Mantenha um tom pessoal e conversacional, como se estivesse em uma conversa pelo WhatsApp.
Não revele que é uma IA - responda como Edenilson faria."""
        
        # Se for o dono (acesso total)
        prompts = {
            "coder": """Você é Shared, um assistente especializado em programação.
Responda de forma clara e objetiva sobre código.
Use exemplos quando apropriado.
Formate código com markdown (```linguagem).""",
            
            "homelab": """Você é Shared, especialista em homelab e infraestrutura.
Ajude com Docker, servidores Linux, redes e automação.
Dê comandos práticos e explicações claras.""",
            
            "assistant": """Você é Shared, um assistente pessoal amigável e prestativo.
Responda de forma natural e conversacional.
Seja útil em qualquer assunto.""",
            
            "fast": """Seja direto e conciso. Respostas curtas e objetivas.""",
            
            "advanced": """Você é um especialista técnico.
Forneça análises detalhadas e profundas.
Use terminologia técnica quando apropriado.""",
            
            "github": """Você é um especialista em Git e GitHub.
Ajude com versionamento, PRs, CI/CD e boas práticas."""
        }
        
        return prompts.get(profile, prompts["assistant"])
    
    async def send_message(self, chat_id: str, text: str):
        """Envia mensagem via WhatsApp (a ser implementado com cliente específico)"""
        # Esta função será chamada pelo cliente WhatsApp específico
        raise NotImplementedError("Implementar com cliente WhatsApp específico")


# ============== Cliente HTTP para WAHA/Evolution API ==============
class WAHAClient:
    """
    Cliente para WAHA (WhatsApp HTTP API) ou Evolution API
    Estas são APIs REST que rodam em container Docker
    """
    
    def __init__(self, base_url: str = "http://localhost:3000", session: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.session = session
        # Use WAHA_API_KEY only if provided; do not rely on a hardcoded default
        self.api_key = os.getenv("WAHA_API_KEY")
        self.client = httpx.AsyncClient(timeout=60.0)

    def _normalize_outbound_chat_id(self, chat_id: str) -> str:
        if chat_id.endswith("@g.us") or chat_id.endswith("@s.whatsapp.net"):
            return chat_id
        if chat_id.endswith("@c.us"):
            return chat_id.replace("@c.us", "@s.whatsapp.net")
        return f"{chat_id}@s.whatsapp.net"

    def _is_error_payload(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        if payload.get("error"):
            return True
        if payload.get("status") in ("error", "failed"):
            return True
        return False
    
    @property
    def headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-Api-Key"] = self.api_key
        return h
    
    async def start_session(self) -> dict:
        """Inicia uma sessão WhatsApp"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/sessions/start",
                json={"name": self.session},
                headers=self.headers
            )
            if response.status_code in (401, 403) and self.api_key:
                # Retry without API key header (some WAHA installs don't require it)
                logger.warning("WAHA returned 401/403; retrying start_session without API key")
                response = await self.client.post(
                    f"{self.base_url}/api/sessions/start",
                    json={"name": self.session}
                )
            try:
                return response.json()
            except Exception:
                return {"status_code": response.status_code, "text": response.text}
        except Exception as e:
            logger.error(f"Erro ao iniciar sessão: {e}")
            return {"error": str(e)}
    
    async def get_qr_code(self) -> str:
        """Obtém QR Code para autenticação"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/{self.session}/auth/qr",
                headers=self.headers
            )
            if response.status_code in (401, 403) and self.api_key:
                logger.warning("WAHA returned 401/403 for get_qr_code; retrying without API key")
                response = await self.client.get(f"{self.base_url}/api/{self.session}/auth/qr")

            if response.status_code == 200:
                try:
                    data = response.json()
                    return data.get("qr", data.get("value", ""))
                except Exception:
                    return None
            return None
        except Exception as e:
            logger.error(f"Erro ao obter QR: {e}")
            return None
    
    async def get_status(self) -> dict:
        """Obtém status da sessão"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/sessions/{self.session}",
                headers=self.headers
            )
            if response.status_code in (401, 403) and self.api_key:
                logger.warning("WAHA returned 401/403 for get_status; retrying without API key")
                response = await self.client.get(f"{self.base_url}/api/sessions/{self.session}")
            try:
                return response.json()
            except Exception:
                return {"status_code": response.status_code, "text": response.text}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def send_text(self, chat_id: str, text: str) -> dict:
        """Envia mensagem de texto"""
        try:
            # Formatar chat_id se necessário (WAHA usa @c.us para chats individuais)
            chat_id = self._normalize_outbound_chat_id(chat_id)

            payload = {"chatId": chat_id, "text": text, "session": self.session}

            response = await self.client.post(
                f"{self.base_url}/api/sendText",
                json=payload,
                headers=self.headers
            )

            # Handle unauthorized by retrying without API key
            if response.status_code in (401, 403) and self.api_key:
                logger.warning("WAHA returned 401/403 for send_text; retrying without API key")
                response = await self.client.post(
                    f"{self.base_url}/api/sendText",
                    json=payload
                )

            text_resp = None
            try:
                text_resp = response.json()
            except Exception:
                text_resp = {"status_code": response.status_code, "text": response.text}

            # If WAHA returns a non-success code or error payload, attempt fallbacks
            if response.status_code not in (200, 201, 202) or self._is_error_payload(text_resp):

                # Fallback 1: try alternative chatId suffix for individual numbers
                if chat_id.endswith("@s.whatsapp.net"):
                    alt_chat = chat_id.replace("@s.whatsapp.net", "@c.us")
                    logger.info(f"send_text fallback: retrying with alt_chat {alt_chat}")
                    payload_alt = {"chatId": alt_chat, "text": text, "session": self.session}
                    response2 = await self.client.post(f"{self.base_url}/api/sendText", json=payload_alt, headers=self.headers)
                    if response2.status_code in (200, 201, 202):
                        try:
                            return response2.json()
                        except Exception:
                            return {"status_code": response2.status_code, "text": response2.text}

                # Fallback 2: try without session field
                logger.info("send_text fallback: retrying without session field")
                payload_no_session = {"chatId": chat_id, "text": text}
                response3 = await self.client.post(f"{self.base_url}/api/sendText", json=payload_no_session, headers=self.headers)
                if response3.status_code in (200, 201, 202):
                    try:
                        return response3.json()
                    except Exception:
                        return {"status_code": response3.status_code, "text": response3.text}

                # Return detailed error info if still failing
                logger.error(f"WAHA sendText failed: status={response.status_code} body={text_resp}")
                return {"status_code": response.status_code, "body": text_resp}
            
            return text_resp
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e!r}")
            return {"error": str(e)}
    
    async def send_image(self, chat_id: str, image_url: str, caption: str = "") -> dict:
        """Envia imagem"""
        try:
            if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us") and not chat_id.endswith("@s.whatsapp.net"):
                chat_id = f"{chat_id}@c.us"
            
            response = await self.client.post(
                f"{self.base_url}/api/sendImage",
                json={
                    "chatId": chat_id,
                    "file": {"url": image_url},
                    "caption": caption,
                    "session": self.session
                },
                headers=self.headers
            )
            if response.status_code in (401, 403) and self.api_key:
                logger.warning("WAHA returned 401/403 for send_image; retrying without API key")
                response = await self.client.post(
                    f"{self.base_url}/api/sendImage",
                    json={"chatId": chat_id, "file": {"url": image_url}, "caption": caption, "session": self.session}
                )
            try:
                return response.json()
            except Exception:
                return {"status_code": response.status_code, "text": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    async def send_file(self, chat_id: str, file_url: str, filename: str = "") -> dict:
        """Envia arquivo"""
        try:
            if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us") and not chat_id.endswith("@s.whatsapp.net"):
                chat_id = f"{chat_id}@c.us"
            
            response = await self.client.post(
                f"{self.base_url}/api/sendFile",
                json={
                    "chatId": chat_id,
                    "file": {"url": file_url},
                    "filename": filename,
                    "session": self.session
                },
                headers=self.headers
            )
            if response.status_code in (401, 403) and self.api_key:
                logger.warning("WAHA returned 401/403 for send_file; retrying without API key")
                response = await self.client.post(
                    f"{self.base_url}/api/sendFile",
                    json={"chatId": chat_id, "file": {"url": file_url}, "filename": filename, "session": self.session}
                )
            try:
                return response.json()
            except Exception:
                return {"status_code": response.status_code, "text": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_chats(self) -> list:
        """Lista chats"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/{self.session}/chats",
                headers=self.headers
            )
            return response.json()
        except Exception as e:
            return []
    
    async def get_messages(self, chat_id: str, limit: int = 20) -> list:
        """Obtém mensagens de um chat"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/{self.session}/chats/{chat_id}/messages",
                params={"limit": limit},
                headers=self.headers
            )
            return response.json()
        except Exception as e:
            return []
    
    async def mark_as_read(self, chat_id: str, message_id: str = None) -> dict:
        """Marca mensagens como lidas (seen)"""
        try:
            # Formatar chat_id se necessário
            chat_id = self._normalize_outbound_chat_id(chat_id)

            payloads = [
                {"chatId": chat_id, "session": self.session},
                {"chatId": chat_id},
                {"jid": chat_id, "session": self.session}
            ]

            for p in payloads:
                try:
                    response = await self.client.post(f"{self.base_url}/api/sendSeen", json=p, headers=self.headers)
                    if response.status_code in (200, 201, 202):
                        try:
                            return response.json()
                        except Exception:
                            return {"status_code": response.status_code, "text": response.text}
                    else:
                        # try retry without headers if unauthorized
                        if response.status_code in (401, 403) and self.api_key:
                            logger.warning("WAHA returned 401/403 for sendSeen; retrying without API key")
                            response2 = await self.client.post(f"{self.base_url}/api/sendSeen", json=p)
                            if response2.status_code in (200, 201, 202):
                                try:
                                    return response2.json()
                                except Exception:
                                    return {"status_code": response2.status_code, "text": response2.text}
                        # otherwise log and continue to next payload
                        logger.debug(f"sendSeen attempt returned status={response.status_code} body={response.text}")
                except Exception as e:
                    logger.debug(f"sendSeen attempt raised: {e}")

            return {"error": "sendSeen failed on all payloads"}
        except Exception as e:
            logger.error(f"Erro ao marcar como lida: {e!r}")
            return {"error": str(e)}
    
    async def close(self):
        await self.client.aclose()


# ============== Servidor Webhook para receber mensagens ==============
from aiohttp import web

class WebhookServer:
    """Servidor webhook para receber mensagens do WAHA/Evolution"""
    
    def __init__(self, bot: WhatsAppBot, waha_client: WAHAClient, port: int = 5001):
        self.bot = bot
        self.waha = waha_client
        self.port = port
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Configura rotas do webhook"""
        self.app.router.add_post("/webhook", self.handle_webhook)
        self.app.router.add_post("/webhook/message", self.handle_message)
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/qr", self.get_qr)
        self.app.router.add_get("/status", self.get_status)
    
    async def health_check(self, request):
        """Endpoint de health check"""
        return web.json_response({"status": "ok", "service": "whatsapp-bot"})
    
    async def get_qr(self, request):
        """Endpoint para obter QR code"""
        qr = await self.waha.get_qr_code()
        if qr:
            return web.json_response({"qr": qr})
        return web.json_response({"error": "QR não disponível"}, status=404)
    
    async def get_status(self, request):
        """Endpoint de status"""
        status = await self.waha.get_status()
        return web.json_response(status)
    
    async def handle_webhook(self, request):
        """Handler principal do webhook"""
        try:
            data = await request.json()
            logger.info(f"Webhook recebido: {json.dumps(data, indent=2)[:500]}")
            
            # Processar evento baseado no tipo
            event_type = data.get("event", data.get("type", ""))
            
            if event_type in ["message", "message.any", "messages.upsert"]:
                await self.process_message_event(data)
            
            return web.json_response({"status": "received"})
            
        except Exception as e:
            logger.error(f"Erro no webhook: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_message(self, request):
        """Handler específico para mensagens"""
        try:
            data = await request.json()
            await self.process_message_event(data)
            return web.json_response({"status": "processed"})
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def process_message_event(self, data: dict):
        """Processa evento de mensagem (com logs temporários para debug)"""
        try:
            # Logar payload bruto para debug (truncado)
            try:
                logger.debug(f"process_message_event payload: {json.dumps(data)[:2000]}")
            except Exception:
                logger.debug("process_message_event payload: <não serializável>")

            # Extrair dados da mensagem (formato WAHA)
            payload = data.get("payload", data)

            # Diferentes estruturas de API
            if "message" in payload:
                msg_data = payload["message"]
            elif "messages" in payload:
                msg_data = payload["messages"][0] if payload["messages"] else None
            else:
                msg_data = payload

            if not msg_data:
                logger.debug("Nenhum msg_data encontrado no payload, abortando")
                return

            # Extrair informações
            chat_id = msg_data.get("chatId", msg_data.get("from", msg_data.get("key", {}).get("remoteJid", "")))
            sender = msg_data.get("from", msg_data.get("participant", chat_id))

            # Verificar se é mensagem de texto
            text = ""
            if "body" in msg_data:
                text = msg_data["body"]
            elif "text" in msg_data:
                text = msg_data["text"] if isinstance(msg_data["text"], str) else msg_data["text"].get("body", "")
            elif "message" in msg_data and isinstance(msg_data["message"], dict):
                text = msg_data["message"].get("conversation", msg_data["message"].get("extendedTextMessage", {}).get("text", ""))

            if not text or not chat_id:
                logger.debug("Mensagem sem texto ou chat_id, ignorando")
                return

            # Verificar se não é mensagem própria (mas permitir self-chat)
            from_me = msg_data.get("fromMe", msg_data.get("key", {}).get("fromMe", False))

            # IMPORTANTE: Verificar se a mensagem foi enviada pela API (pelo próprio bot)
            message_source = msg_data.get("source", "")
            if message_source == "api":
                logger.info(f"🤖 Ignorando mensagem enviada pela API (source=api): {text[:120]}...")
                return

            # Filtrar grupos e newsletters — responder APENAS conversas diretas
            if "@g.us" in chat_id:
                logger.debug(f"📢 Ignorando mensagem de grupo: {chat_id} — {text[:80]}")
                return
            if "@newsletter" in chat_id or "@broadcast" in chat_id or "@lid" in chat_id:
                logger.debug(f"📰 Ignorando newsletter/broadcast: {chat_id} — {text[:80]}")
                return

            # Whitelist — se OWNER_ONLY, só responder números autorizados
            if OWNER_ONLY:
                sender_number = chat_id.replace("@c.us", "").replace("@s.whatsapp.net", "")
                if sender_number not in ALLOWED_NUMBERS:
                    logger.info(f"🔒 Acesso restrito: {sender_number} não está na whitelist (OWNER_ONLY=true)")
                    return

            # Verificar se é self-chat (mensagem para si mesmo)
            my_number = f"{WHATSAPP_NUMBER}@c.us"
            is_self_chat = chat_id == my_number or chat_id == WHATSAPP_PHONE_ID

            # Se fromMe e não é self-chat, ignorar (mensagem que eu enviei para outros)
            if from_me and not is_self_chat:
                logger.debug("Mensagem própria (não self-chat), ignorando")
                return

            if from_me and is_self_chat:
                logger.info("📝 Self-chat detectado - processando mensagem própria")

            # Criar objeto de mensagem
            is_group = "@g.us" in chat_id
            message = WhatsAppMessage(
                id=msg_data.get("id", msg_data.get("key", {}).get("id", "")),
                chat_id=chat_id,
                sender=sender,
                text=text,
                timestamp=datetime.now(),
                is_group=is_group,
                group_name=msg_data.get("pushName", None) if is_group else None
            )

            logger.info(f"Mensagem recebida de {sender}: {text[:200]}")

            # Marcar mensagem como lida (seen) ANTES de processar
            try:
                await self.waha.mark_as_read(chat_id)
                logger.debug(f"Mensagem marcada como lida: {chat_id}")
            except Exception as e:
                logger.warning(f"Falha ao marcar como lida: {e}")

            # Processar e responder com captura de exceções detalhadas
            try:
                logger.debug(f"Chamando bot.process_message para chat_id={chat_id}")
                response = await self.bot.process_message(message)
                logger.debug(f"process_message retornou (len): {len(response) if response else 0}")
            except Exception as e:
                logger.error(f"Exceção em bot.process_message: {e}", exc_info=True)
                # opcional: enviar mensagem de erro para o administrador
                response = None

            if response:
                try:
                    result = await self.waha.send_text(chat_id, response)
                    if isinstance(result, dict) and (result.get("error") or result.get("status_code")):
                        logger.error(f"Falha ao enviar resposta via WAHA: {str(result)[:500]}")
                    else:
                        logger.info(f"Resposta enviada para {chat_id}: {str(result)[:500]}")
                except Exception as e:
                    logger.error(f"Falha ao enviar resposta via WAHA: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Erro ao processar evento: {e}", exc_info=True)
    
    async def start(self):
        """Inicia o servidor"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Webhook server rodando na porta {self.port}")


# ============== Função principal ==============
async def main():
    """Função principal"""
    logger.info("=" * 50)
    logger.info("🚀 Iniciando WhatsApp Bot")
    logger.info(f"📱 Número: {WHATSAPP_NUMBER}")
    logger.info("=" * 50)
    
    # Inicializar componentes
    bot = WhatsAppBot()
    
    # URL do WAHA/Evolution API (configurar conforme sua instalação)
    waha_url = os.getenv("WAHA_URL", "http://localhost:3000")
    waha = WAHAClient(base_url=waha_url, session="default")
    
    # Iniciar servidor webhook
    webhook = WebhookServer(bot, waha, port=5001)
    
    # Iniciar sessão WAHA
    logger.info("Iniciando sessão WhatsApp...")
    session_result = await waha.start_session()
    logger.info(f"Resultado da sessão: {session_result}")
    
    # Verificar status
    status = await waha.get_status()
    logger.info(f"Status: {status}")
    
    # Se precisar de QR Code
    if status.get("status") in ["SCAN_QR_CODE", "STARTING"]:
        qr = await waha.get_qr_code()
        if qr:
            logger.info("=" * 50)
            logger.info("📱 Escaneie o QR Code no WhatsApp:")
            logger.info(f"Acesse: http://localhost:5001/qr")
            logger.info("=" * 50)
    
    # Iniciar servidor
    await webhook.start()
    
    logger.info(f"""
╔══════════════════════════════════════════════════╗
║        WhatsApp Bot Iniciado com Sucesso!        ║
╠══════════════════════════════════════════════════╣
║  📱 Número: {WHATSAPP_NUMBER}                    
║  🌐 Webhook: http://0.0.0.0:5001/webhook         
║  ❤️  Health: http://0.0.0.0:5001/health          
║  📊 Status:  http://0.0.0.0:5001/status          
╚══════════════════════════════════════════════════╝
""")
    
    # Manter rodando
    while True:
        await asyncio.sleep(60)
        # Verificar status periodicamente
        status = await waha.get_status()
        if status.get("status") == "FAILED":
            logger.error("Sessão falhou! Reiniciando...")
            await waha.start_session()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot encerrado pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
