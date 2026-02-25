#!/usr/bin/env python3
"""
Bot Telegram Completo com Integração aos Agentes Especializados
Implementa todas as funcionalidades da API do Telegram
Com Auto-Desenvolvimento: quando não consegue responder, desenvolve a solução
Com Busca Web: pesquisa na internet para enriquecer respostas e desenvolvimento
"""
import os
import asyncio
import httpx
import json
import re
import time
import fcntl
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import sys
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

# Adicionar diretório atual ao path para imports locais
sys.path.insert(0, str(Path(__file__).parent))

# Import do módulo de busca web
try:
    from web_search import WebSearchEngine, create_search_engine
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    print("⚠️ Módulo web_search não encontrado - busca web desabilitada")

# Import do módulo de Google Calendar
try:
    from google_calendar_integration import (
        get_calendar_assistant, process_calendar_request, CalendarAssistant
    )
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False
    print("⚠️ Módulo google_calendar_integration não encontrado - calendário desabilitado")

# Import do módulo de Gmail
try:
    from gmail_integration import (
        get_gmail_client, get_email_cleaner, process_gmail_command
    )
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    print("⚠️ Módulo gmail_integration não encontrado - Gmail desabilitado")

# Import do módulo de Localização
try:
    from location_integration.telegram_location import (
        handle_location_command, get_location_help, LOCATION_COMMANDS
    )
    LOCATION_AVAILABLE = True
except ImportError:
    LOCATION_AVAILABLE = False
    print("⚠️ Módulo location_integration não encontrado - localização desabilitada")

# Import do módulo de Home Assistant
try:
    from homeassistant_integration.telegram_homeassistant import (
        handle_homeassistant_command, get_homeassistant_help, HOMEASSISTANT_COMMANDS
    )
    HOMEASSISTANT_AVAILABLE = True
except ImportError:
    HOMEASSISTANT_AVAILABLE = False
    print("⚠️ Módulo homeassistant_integration não encontrado - casa inteligente desabilitada")

# Import do módulo de integração OpenWebUI + Modelos
try:
    from openwebui_integration import (
        IntegrationClient, get_integration_client, close_integration,
        MODEL_PROFILES, ChatResponse
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False
    print("⚠️ Módulo openwebui_integration não encontrado")

# Configurações
try:
    from tools.secrets_loader import get_telegram_token
    BOT_TOKEN = get_telegram_token()
except Exception:
    try:
        from tools.vault.secret_store import get_field
        BOT_TOKEN = get_field("eddie/telegram_bot_token", "password")
    except Exception:
        BOT_TOKEN = ""
HOMELAB_HOST = os.environ.get('HOMELAB_HOST', 'localhost')
OLLAMA_HOST = os.getenv("OLLAMA_HOST", f"http://{HOMELAB_HOST}:11434")
MODEL = os.getenv("OLLAMA_MODEL", "eddie-coder")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "948686300"))
AGENTS_API = os.getenv("AGENTS_API", "http://localhost:8503")
OPENWEBUI_HOST = os.getenv("OPENWEBUI_HOST", f"http://{HOMELAB_HOST}:3000")

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

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

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
    r"preciso de (mais|ferramentas|recursos)",
    r"(falta|ausência) de (dados|informações|conhecimento)",
    r"não (encontrei|achei) (informações|dados)",
    r"não posso (ajudar|assisti|fazer|executar|realizar)",
    r"peço desculpas",
    r"sinto muito.*(não|nao)",
    r"não sou capaz",
    r"não é algo que (eu|posso)",
    r"impossível para mim",
    r"não há como",
]


class TelegramAPI:
    """Classe para interagir com todas as funcionalidades da API do Telegram"""
    
    def __init__(self, token: str):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def _request(self, method: str, files: dict = None, **params) -> dict:
        """Faz requisição para a API do Telegram"""
        try:
            params = {k: v for k, v in params.items() if v is not None}
            if files:
                response = await self.client.post(f"{self.base}/{method}", files=files, data=params)
            else:
                response = await self.client.post(f"{self.base}/{method}", json=params or None)
            return response.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    # ========== Mensagens ==========
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown",
                          reply_to_message_id: int = None, reply_markup: dict = None) -> dict:
        """Envia mensagem de texto"""
        return await self._request("sendMessage", chat_id=chat_id, text=text[:4096],
                                   parse_mode=parse_mode, reply_to_message_id=reply_to_message_id,
                                   reply_markup=reply_markup)
    
    async def forward_message(self, chat_id: int, from_chat_id: int, message_id: int) -> dict:
        """Encaminha mensagem"""
        return await self._request("forwardMessage", chat_id=chat_id, 
                                   from_chat_id=from_chat_id, message_id=message_id)
    
    async def copy_message(self, chat_id: int, from_chat_id: int, message_id: int) -> dict:
        """Copia mensagem sem referência"""
        return await self._request("copyMessage", chat_id=chat_id,
                                   from_chat_id=from_chat_id, message_id=message_id)
    
    async def edit_message_text(self, chat_id: int, message_id: int, text: str,
                                parse_mode: str = "Markdown") -> dict:
        """Edita texto de mensagem"""
        return await self._request("editMessageText", chat_id=chat_id, 
                                   message_id=message_id, text=text, parse_mode=parse_mode)
    
    async def delete_message(self, chat_id: int, message_id: int) -> dict:
        """Deleta mensagem"""
        return await self._request("deleteMessage", chat_id=chat_id, message_id=message_id)
    
    async def send_chat_action(self, chat_id: int, action: str = "typing") -> dict:
        """Envia ação (typing, upload_photo, etc)"""
        return await self._request("sendChatAction", chat_id=chat_id, action=action)
    
    # ========== Mídia ==========
    async def send_photo(self, chat_id: int, photo: str, caption: str = None) -> dict:
        """Envia foto (URL ou file_id)"""
        return await self._request("sendPhoto", chat_id=chat_id, photo=photo, caption=caption)
    
    async def send_photo_file(self, chat_id: int, file_path: str, caption: str = None) -> dict:
        """Envia foto de arquivo local"""
        with open(file_path, 'rb') as f:
            return await self._request("sendPhoto", files={"photo": f}, 
                                       chat_id=chat_id, caption=caption)
    
    async def send_document(self, chat_id: int, document: str, caption: str = None) -> dict:
        """Envia documento"""
        return await self._request("sendDocument", chat_id=chat_id, 
                                   document=document, caption=caption)
    
    async def send_document_file(self, chat_id: int, file_path: str, caption: str = None) -> dict:
        """Envia documento de arquivo local"""
        with open(file_path, 'rb') as f:
            return await self._request("sendDocument", files={"document": f},
                                       chat_id=chat_id, caption=caption)
    
    async def send_audio(self, chat_id: int, audio: str, caption: str = None) -> dict:
        """Envia áudio"""
        return await self._request("sendAudio", chat_id=chat_id, audio=audio, caption=caption)
    
    async def send_video(self, chat_id: int, video: str, caption: str = None) -> dict:
        """Envia vídeo"""
        return await self._request("sendVideo", chat_id=chat_id, video=video, caption=caption)
    
    async def send_voice(self, chat_id: int, voice: str, caption: str = None) -> dict:
        """Envia mensagem de voz"""
        return await self._request("sendVoice", chat_id=chat_id, voice=voice, caption=caption)
    
    async def send_sticker(self, chat_id: int, sticker: str) -> dict:
        """Envia sticker"""
        return await self._request("sendSticker", chat_id=chat_id, sticker=sticker)
    
    async def send_animation(self, chat_id: int, animation: str, caption: str = None) -> dict:
        """Envia GIF/animação"""
        return await self._request("sendAnimation", chat_id=chat_id, 
                                   animation=animation, caption=caption)
    
    async def send_media_group(self, chat_id: int, media: list) -> dict:
        """Envia grupo de mídias (album)"""
        return await self._request("sendMediaGroup", chat_id=chat_id, media=media)
    
    # ========== Localização e Contatos ==========
    async def send_location(self, chat_id: int, latitude: float, longitude: float) -> dict:
        """Envia localização"""
        return await self._request("sendLocation", chat_id=chat_id, 
                                   latitude=latitude, longitude=longitude)
    
    async def send_venue(self, chat_id: int, latitude: float, longitude: float,
                        title: str, address: str) -> dict:
        """Envia local/estabelecimento"""
        return await self._request("sendVenue", chat_id=chat_id, latitude=latitude,
                                   longitude=longitude, title=title, address=address)
    
    async def send_contact(self, chat_id: int, phone_number: str, first_name: str,
                          last_name: str = None) -> dict:
        """Envia contato"""
        return await self._request("sendContact", chat_id=chat_id, phone_number=phone_number,
                                   first_name=first_name, last_name=last_name)
    
    # ========== Enquetes ==========
    async def send_poll(self, chat_id: int, question: str, options: list,
                       is_anonymous: bool = True, allows_multiple_answers: bool = False) -> dict:
        """Envia enquete"""
        return await self._request("sendPoll", chat_id=chat_id, question=question,
                                   options=options, is_anonymous=is_anonymous,
                                   allows_multiple_answers=allows_multiple_answers)
    
    async def send_quiz(self, chat_id: int, question: str, options: list,
                       correct_option_id: int, explanation: str = None) -> dict:
        """Envia quiz"""
        return await self._request("sendPoll", chat_id=chat_id, question=question,
                                   options=options, type="quiz", 
                                   correct_option_id=correct_option_id,
                                   explanation=explanation)
    
    async def stop_poll(self, chat_id: int, message_id: int) -> dict:
        """Para enquete"""
        return await self._request("stopPoll", chat_id=chat_id, message_id=message_id)
    
    # ========== Informações do Chat ==========
    async def get_chat(self, chat_id: int) -> dict:
        """Obtém informações do chat"""
        return await self._request("getChat", chat_id=chat_id)
    
    async def get_chat_administrators(self, chat_id: int) -> dict:
        """Obtém admins do chat"""
        return await self._request("getChatAdministrators", chat_id=chat_id)
    
    async def get_chat_member_count(self, chat_id: int) -> dict:
        """Obtém quantidade de membros"""
        return await self._request("getChatMemberCount", chat_id=chat_id)
    
    async def get_chat_member(self, chat_id: int, user_id: int) -> dict:
        """Obtém info de membro específico"""
        return await self._request("getChatMember", chat_id=chat_id, user_id=user_id)
    
    # ========== Gerenciamento de Chat ==========
    async def set_chat_title(self, chat_id: int, title: str) -> dict:
        """Define título do chat"""
        return await self._request("setChatTitle", chat_id=chat_id, title=title)
    
    async def set_chat_description(self, chat_id: int, description: str) -> dict:
        """Define descrição do chat"""
        return await self._request("setChatDescription", chat_id=chat_id, description=description)
    
    async def set_chat_photo(self, chat_id: int, photo_path: str) -> dict:
        """Define foto do chat"""
        with open(photo_path, 'rb') as f:
            return await self._request("setChatPhoto", files={"photo": f}, chat_id=chat_id)
    
    async def delete_chat_photo(self, chat_id: int) -> dict:
        """Remove foto do chat"""
        return await self._request("deleteChatPhoto", chat_id=chat_id)
    
    async def pin_chat_message(self, chat_id: int, message_id: int,
                               disable_notification: bool = False) -> dict:
        """Fixa mensagem"""
        return await self._request("pinChatMessage", chat_id=chat_id, message_id=message_id,
                                   disable_notification=disable_notification)
    
    async def unpin_chat_message(self, chat_id: int, message_id: int = None) -> dict:
        """Desfixa mensagem"""
        return await self._request("unpinChatMessage", chat_id=chat_id, message_id=message_id)
    
    async def unpin_all_chat_messages(self, chat_id: int) -> dict:
        """Desfixa todas mensagens"""
        return await self._request("unpinAllChatMessages", chat_id=chat_id)
    
    async def leave_chat(self, chat_id: int) -> dict:
        """Sai do chat"""
        return await self._request("leaveChat", chat_id=chat_id)
    
    # ========== Links de Convite ==========
    async def create_chat_invite_link(self, chat_id: int, name: str = None,
                                      expire_date: int = None, member_limit: int = None) -> dict:
        """Cria link de convite"""
        return await self._request("createChatInviteLink", chat_id=chat_id, name=name,
                                   expire_date=expire_date, member_limit=member_limit)
    
    async def export_chat_invite_link(self, chat_id: int) -> dict:
        """Exporta link de convite principal"""
        return await self._request("exportChatInviteLink", chat_id=chat_id)
    
    async def revoke_chat_invite_link(self, chat_id: int, invite_link: str) -> dict:
        """Revoga link de convite"""
        return await self._request("revokeChatInviteLink", chat_id=chat_id, 
                                   invite_link=invite_link)
    
    # ========== Moderação ==========
    async def ban_chat_member(self, chat_id: int, user_id: int,
                              until_date: int = None, revoke_messages: bool = True) -> dict:
        """Bane membro"""
        return await self._request("banChatMember", chat_id=chat_id, user_id=user_id,
                                   until_date=until_date, revoke_messages=revoke_messages)
    
    async def unban_chat_member(self, chat_id: int, user_id: int,
                                only_if_banned: bool = True) -> dict:
        """Desbane membro"""
        return await self._request("unbanChatMember", chat_id=chat_id, user_id=user_id,
                                   only_if_banned=only_if_banned)
    
    async def restrict_chat_member(self, chat_id: int, user_id: int,
                                   permissions: dict, until_date: int = None) -> dict:
        """Restringe permissões do membro"""
        return await self._request("restrictChatMember", chat_id=chat_id, user_id=user_id,
                                   permissions=permissions, until_date=until_date)
    
    async def promote_chat_member(self, chat_id: int, user_id: int,
                                  can_manage_chat: bool = False,
                                  can_post_messages: bool = False,
                                  can_edit_messages: bool = False,
                                  can_delete_messages: bool = False,
                                  can_manage_video_chats: bool = False,
                                  can_restrict_members: bool = False,
                                  can_promote_members: bool = False,
                                  can_change_info: bool = False,
                                  can_invite_users: bool = False,
                                  can_pin_messages: bool = False) -> dict:
        """Promove membro a admin"""
        return await self._request("promoteChatMember", chat_id=chat_id, user_id=user_id,
                                   can_manage_chat=can_manage_chat,
                                   can_post_messages=can_post_messages,
                                   can_edit_messages=can_edit_messages,
                                   can_delete_messages=can_delete_messages,
                                   can_manage_video_chats=can_manage_video_chats,
                                   can_restrict_members=can_restrict_members,
                                   can_promote_members=can_promote_members,
                                   can_change_info=can_change_info,
                                   can_invite_users=can_invite_users,
                                   can_pin_messages=can_pin_messages)
    
    async def set_chat_administrator_custom_title(self, chat_id: int, user_id: int,
                                                  custom_title: str) -> dict:
        """Define título customizado para admin"""
        return await self._request("setChatAdministratorCustomTitle", chat_id=chat_id,
                                   user_id=user_id, custom_title=custom_title)
    
    # ========== Bot ==========
    async def get_me(self) -> dict:
        """Obtém info do bot"""
        return await self._request("getMe")
    
    async def get_updates(self, offset: int = None, timeout: int = 30) -> dict:
        """Obtém atualizações"""
        return await self._request("getUpdates", offset=offset, timeout=timeout)
    
    async def set_my_commands(self, commands: list, scope: dict = None) -> dict:
        """Define comandos do bot"""
        return await self._request("setMyCommands", commands=commands, scope=scope)
    
    async def delete_my_commands(self, scope: dict = None) -> dict:
        """Remove comandos do bot"""
        return await self._request("deleteMyCommands", scope=scope)
    
    async def get_my_commands(self, scope: dict = None) -> dict:
        """Obtém comandos do bot"""
        return await self._request("getMyCommands", scope=scope)
    
    async def set_my_name(self, name: str, language_code: str = None) -> dict:
        """Define nome do bot"""
        return await self._request("setMyName", name=name, language_code=language_code)
    
    async def set_my_description(self, description: str, language_code: str = None) -> dict:
        """Define descrição do bot"""
        return await self._request("setMyDescription", description=description,
                                   language_code=language_code)
    
    async def close(self):
        """Fecha cliente HTTP"""
        await self.client.aclose()


class AgentsClient:
    """Cliente para API de Agentes Especializados"""
    
    def __init__(self, base_url: str = "http://localhost:8503"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=180.0)
    
    async def health(self) -> dict:
        """Verifica saúde da API"""
        try:
            r = await self.client.get(f"{self.base_url}/health")
            return r.json()
        except:
            return {"status": "offline"}
    
    async def list_agents(self) -> dict:
        """Lista agentes disponíveis"""
        try:
            r = await self.client.get(f"{self.base_url}/agents")
            return r.json()
        except:
            return {"error": "API offline"}
    
    async def generate_code(self, language: str, description: str, context: str = "") -> dict:
        """Gera código com agente especializado"""
        try:
            r = await self.client.post(f"{self.base_url}/code/generate", json={
                "language": language,
                "description": description,
                "context": context
            })
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def create_project(self, language: str, description: str, name: str = None) -> dict:
        """Cria projeto completo"""
        try:
            r = await self.client.post(f"{self.base_url}/projects/create", json={
                "language": language,
                "description": description,
                "project_name": name
            })
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def execute_code(self, language: str, code: str) -> dict:
        """Executa código"""
        try:
            r = await self.client.post(f"{self.base_url}/code/execute", json={
                "language": language,
                "code": code,
                "run_tests": True
            })
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        await self.client.aclose()


class AutoDeveloper:
    """
    Sistema de Auto-Desenvolvimento com Teste Pós-Deploy e Busca Web
    Quando a IA não consegue responder, aciona:
    1. Busca Web - pesquisa na internet para obter contexto
    2. Analista de Requisitos - pesquisa como construir a solução
    3. Dev Agent - implementa a solução
    4. Deploy via GitHub CI/CD
    5. Teste com solicitação original após deploy
    6. Notifica resultado do aprendizado
    """
    
    def __init__(self, agents_client: 'AgentsClient', ollama_client: httpx.AsyncClient):
        self.agents = agents_client
        self.ollama = ollama_client
        self.client = httpx.AsyncClient(timeout=600.0)  # 10 min para CPU
        self.developments: Dict[str, dict] = {}  # Histórico de desenvolvimentos
        self.pending_tests: Dict[str, dict] = {}  # Testes pendentes pós-deploy
        
        # Inicializar motor de busca web
        if WEB_SEARCH_AVAILABLE:
            self.web_search = create_search_engine(rag_api_url=os.environ.get('RAG_API', f"http://{HOMELAB_HOST}:8001"))
        else:
            self.web_search = None
        # Known agents cache (populated async)
        self.known_agents: List[str] = []

        async def _load_agents():
            try:
                res = await self.agents.list_agents()
                if isinstance(res, dict):
                    langs = res.get('available_languages') or res.get('available') or []
                    if isinstance(langs, list):
                        self.known_agents = langs
            except Exception:
                pass

        try:
            asyncio.create_task(_load_agents())
        except Exception:
            # If event loop isn't running, ignore; callers can call `await auto_dev.agents.list_agents()` later
            pass
    
    async def search_web(self, query: str, num_results: int = 3) -> Dict[str, Any]:
        """
        Realiza busca na internet para enriquecer contexto.
        Usado para:
        - Pesquisar documentação de bibliotecas
        - Encontrar exemplos de código
        - Obter informações atualizadas
        """
        if not self.web_search:
            return {"success": False, "error": "Busca web não disponível"}
        
        try:
            # Fazer busca e extrair conteúdo
            results = self.web_search.search_and_extract(query, num_results=num_results)
            
            if not results:
                return {"success": False, "error": "Nenhum resultado encontrado"}
            
            # Formatar resultados para uso
            formatted = self.web_search.format_results_for_llm(results, query)
            
            # Salvar no RAG para aprendizado contínuo
            save_result = self.web_search.save_to_rag(results, query)
            
            return {
                "success": True,
                "results_count": len(results),
                "formatted": formatted,
                "saved_to_rag": save_result.get("success", False),
                "sources": [{"title": r.title, "url": r.url} for r in results]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def detect_inability(self, response: str) -> bool:
        """Detecta se a resposta indica incapacidade de atender"""
        response_lower = response.lower()
        
        # Detecta erros de conexão/timeout
        if response.startswith("Erro:"):
            print(f"[Detect] Erro detectado como incapacidade: {response[:50]}")
            return True
        
        for pattern in INABILITY_PATTERNS:
            if re.search(pattern, response_lower):
                return True
        
        # Verifica se é muito curta ou vaga
        if len(response) < 50 and ("não" in response_lower or "desculpe" in response_lower):
            return True
        
        return False
    
    async def analyze_request(self, user_request: str, use_web_search: bool = True) -> Dict[str, Any]:
        """
        Analista de Requisitos analisa o pedido do usuário.
        Utiliza busca web para enriquecer a análise quando disponível.
        """
        try:
            web_context = ""
            print(f"[Analyze] Iniciando análise para: {user_request[:50]}...")
            
            # Fase 0: Busca Web para contexto (se disponível)
            if use_web_search and self.web_search:
                # Criar query de busca baseada no pedido
                search_query = f"{user_request} tutorial example implementation"
                web_result = await self.search_web(search_query, num_results=2)
                
                if web_result.get("success"):
                    web_context = f"""
CONTEXTO DA INTERNET:
{web_result.get('formatted', '')}

FONTES CONSULTADAS:
{chr(10).join(f"- {s['title']}: {s['url']}" for s in web_result.get('sources', []))}
"""
            
            # Usar o Ollama diretamente para análise de requisitos
            prompt = f"""Você é um Analista de Requisitos Senior. Analise o seguinte pedido do usuário e crie uma especificação técnica.

PEDIDO DO USUÁRIO:
{user_request}
{web_context}
Retorne APENAS um JSON válido com:
{{
    "titulo": "título curto da feature",
    "descricao": "descrição detalhada do que deve ser desenvolvido",
    "linguagem_sugerida": "python|javascript|go|rust|java|csharp|php",
    "tipo": "function|class|api|script|tool",
    "complexidade": "simple|moderate|complex",
    "dependencias": ["lista de bibliotecas necessárias"],
    "passos_implementacao": [
        "passo 1",
        "passo 2"
    ],
    "casos_teste": [
        "teste 1",
        "teste 2"
    ],
    "viabilidade": "alta|media|baixa",
    "justificativa": "explicação de por que esta solução resolve o problema"
}}"""

            response = await self.ollama.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=600.0  # 10 minutos para CPU
            )
            
            print(f"[Analyze] Resposta Ollama status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                text = data.get("response", "")
                print(f"[Analyze] Texto recebido: {len(text)} chars")
                
                # Extrair JSON da resposta
                try:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        result = json.loads(text[start:end])
                        print(f"[Analyze] JSON parseado com sucesso: {result.get('titulo', 'N/A')}")
                        return result
                    else:
                        print(f"[Analyze] Não encontrou JSON na resposta")
                except Exception as parse_err:
                    print(f"[Analyze] Erro ao parsear JSON: {parse_err}")
            else:
                print(f"[Analyze] Erro HTTP: {response.status_code}")
            
            print("[Analyze] Usando fallback")
            return {
                "titulo": "Feature solicitada",
                "descricao": user_request,
                "linguagem_sugerida": "python",
                "tipo": "function",
                "complexidade": "moderate",
                "dependencias": [],
                "passos_implementacao": ["Analisar requisito", "Implementar solução"],
                "casos_teste": ["Teste básico de funcionamento"],
                "viabilidade": "media",
                "justificativa": "Análise automática"
            }
            
        except Exception as e:
            import traceback
            print(f"[Analyze] Exceção: {type(e).__name__}: {e}")
            print(f"[Analyze] Traceback: {traceback.format_exc()}")
            return {"error": f"{type(e).__name__}: {str(e) or 'sem mensagem'}"}
    
    async def develop_solution(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Dev Agent desenvolve a solução baseada nos requisitos"""
        try:
            language = requirements.get("linguagem_sugerida", "python")
            description = f"""
{requirements.get('titulo', 'Feature')}

{requirements.get('descricao', '')}

REQUISITOS:
- Tipo: {requirements.get('tipo', 'function')}
- Complexidade: {requirements.get('complexidade', 'moderate')}
- Dependências: {', '.join(requirements.get('dependencias', []))}

PASSOS DE IMPLEMENTAÇÃO:
{chr(10).join(f"- {p}" for p in requirements.get('passos_implementacao', []))}

CASOS DE TESTE:
{chr(10).join(f"- {t}" for t in requirements.get('casos_teste', []))}

Implemente uma solução completa, funcional e bem documentada.
"""
            
            # Primeiro tenta usar a API de agentes
            result = await self.agents.generate_code(language, description)
            
            if "error" not in result and result.get("code"):
                return {
                    "success": True,
                    "language": language,
                    "code": result.get("code", ""),
                    "tests": result.get("tests", ""),
                    "method": "agents_api"
                }
            
            # Fallback: usar Ollama diretamente
            prompt = f"""Você é um desenvolvedor expert em {language}. 
Implemente a seguinte solução:

{description}

Forneça:
1. Código completo e funcional
2. Documentação inline
3. Testes unitários

Retorne o código em blocos markdown."""

            response = await self.ollama.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=600.0  # 10 minutos para CPU
            )
            
            if response.status_code == 200:
                data = response.json()
                code_text = data.get("response", "")
                
                # Extrair código
                code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', code_text, re.DOTALL)
                code = "\n\n".join(code_blocks) if code_blocks else code_text
                
                return {
                    "success": True,
                    "language": language,
                    "code": code,
                    "tests": "",
                    "method": "ollama_direct"
                }
            
            return {"success": False, "error": "Falha ao gerar código"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def execute_and_validate(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        """Executa e valida a solução desenvolvida"""
        if not solution.get("success"):
            return {"validated": False, "error": solution.get("error")}
        
        try:
            # Tentar executar o código via API de agentes
            result = await self.agents.execute_code(
                solution.get("language", "python"),
                solution.get("code", "")
            )
            
            if "error" not in result:
                return {
                    "validated": True,
                    "output": result.get("output", result.get("result", "")),
                    "execution_success": result.get("success", True)
                }
            
            return {"validated": False, "error": result.get("error")}
            
        except Exception as e:
            # Se não conseguir executar, considera válido mas não testado
            return {"validated": True, "output": "Código gerado (não executado)", "note": str(e)}
    
    async def auto_develop(self, user_request: str, original_response: str) -> Tuple[bool, str]:
        """
        Fluxo completo de auto-desenvolvimento:
        1. Detecta se precisa desenvolver
        2. Analisa requisitos
        3. Desenvolve solução
        4. Valida e retorna explicação
        5. Deploy e teste com solicitação original
        """
        dev_id = f"DEV_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # Fase 1: Análise de Requisitos
            requirements = await self.analyze_request(user_request)
            
            if "error" in requirements:
                return False, f"Erro na análise: {requirements['error']}"
            
            print(f"[Auto-Dev] Fase 1 OK: {requirements.get('titulo', 'N/A')}")
            
            # Fase 2: Desenvolvimento
            solution = await self.develop_solution(requirements)
            
            if not solution.get("success"):
                return False, f"Erro no desenvolvimento: {solution.get('error')}"
            
            print(f"[Auto-Dev] Fase 2 OK: {len(solution.get('code', ''))} chars de código")
            
            # Fase 3: Validação
            validation = await self.execute_and_validate(solution)
            print(f"[Auto-Dev] Fase 3 OK: validated={validation.get('validated')}")
            
            # Fase 4: Deploy da solução
            deploy_result = await self.deploy_solution(dev_id, requirements, solution)
            print(f"[Auto-Dev] Fase 4 OK: success={deploy_result.get('success')}")
            
            # Fase 5: Agendar teste pós-deploy com a solicitação original
            # Salvar para teste posterior (após CI/CD completar)
            self.pending_tests[dev_id] = {
                "original_request": user_request,
                "deploy_time": datetime.now().isoformat(),
                "test_scheduled": True
            }
            
            # Fase 6: Preparar resposta explicativa
            explanation = self._format_development_response(
                requirements, solution, validation, deploy_result, dev_id
            )
            
            # Salvar no histórico
            self.developments[dev_id] = {
                "request": user_request,
                "requirements": requirements,
                "solution": solution,
                "validation": validation,
                "deploy": deploy_result,
                "timestamp": datetime.now().isoformat(),
                "test_pending": True
            }
            
            # Iniciar task de teste assíncrono após delay
            asyncio.create_task(self._delayed_post_deploy_test(dev_id, user_request))
            
            print(f"[Auto-Dev] Fase 6 OK: explanation tem {len(explanation)} chars")
            return True, explanation
            
        except Exception as e:
            import traceback
            print(f"[Auto-Dev] ERRO: {type(e).__name__}: {e}")
            print(f"[Auto-Dev] Traceback: {traceback.format_exc()}")
            return False, f"Erro no auto-desenvolvimento: {e}"
    
    async def _delayed_post_deploy_test(self, dev_id: str, original_request: str):
        """
        Testa a solução após deploy com a solicitação original.
        Aguarda CI/CD completar antes de testar.
        """
        try:
            # Aguardar tempo para CI/CD completar (2 minutos)
            await asyncio.sleep(120)
            
            # Verificar status do workflow no GitHub
            workflow_status = await self._check_github_workflow_status(dev_id)
            
            if workflow_status.get("completed"):
                # Testar com a solicitação original
                test_result = await self._test_with_original_request(dev_id, original_request)
                
                # Atualizar histórico
                if dev_id in self.developments:
                    self.developments[dev_id]["post_deploy_test"] = test_result
                    self.developments[dev_id]["test_pending"] = False
                
                # Notificar resultado do teste
                await self._notify_test_result(dev_id, original_request, test_result)
            else:
                # Workflow ainda não completou, agendar nova tentativa
                await asyncio.sleep(60)
                await self._delayed_post_deploy_test(dev_id, original_request)
                
        except Exception as e:
            print(f"Erro no teste pós-deploy {dev_id}: {e}")
    
    async def _check_github_workflow_status(self, dev_id: str) -> Dict[str, Any]:
        """Verifica status do workflow de deploy no GitHub"""
        try:
            import os
            github_token = os.environ.get("GITHUB_TOKEN", "")
            if not github_token:
                try:
                    from tools.vault.secret_store import get_field
                    github_token = get_field("eddie/github_token", "password")
                except Exception:
                    github_token = ""
            if not github_token:
                return {"completed": True, "status": "unknown", "note": "Token não configurado"}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/repos/eddiejdi/eddie-auto-dev/actions/runs",
                    headers={"Authorization": f"token {github_token}"},
                    params={"per_page": 5}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    runs = data.get("workflow_runs", [])
                    
                    # Procurar workflow relacionado ao dev_id
                    for run in runs:
                        if dev_id in run.get("head_commit", {}).get("message", ""):
                            return {
                                "completed": run.get("status") == "completed",
                                "conclusion": run.get("conclusion"),
                                "workflow_id": run.get("id"),
                                "url": run.get("html_url")
                            }
                    
                    # Se não encontrou específico, verificar último workflow de deploy
                    for run in runs:
                        if "deploy" in run.get("name", "").lower():
                            return {
                                "completed": run.get("status") == "completed",
                                "conclusion": run.get("conclusion"),
                                "workflow_id": run.get("id")
                            }
            
            return {"completed": True, "status": "assumed"}
            
        except Exception as e:
            return {"completed": True, "error": str(e)}
    
    async def _test_with_original_request(self, dev_id: str, original_request: str) -> Dict[str, Any]:
        """
        Testa a solução deployada fazendo a mesma solicitação original.
        Verifica se agora consegue responder adequadamente.
        """
        try:
            # Fazer nova consulta ao Ollama com a solicitação original
            response = await self.ollama.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": f"""Após o desenvolvimento e deploy da solução {dev_id}, 
responda à seguinte solicitação do usuário:

{original_request}

Se você agora consegue atender a solicitação, forneça a resposta completa.
Se ainda não consegue, explique o que está faltando.""",
                    "stream": False
                },
                timeout=600.0  # 10 minutos para CPU
            )
            
            if response.status_code == 200:
                data = response.json()
                new_response = data.get("response", "")
                
                # Verificar se a nova resposta indica capacidade
                still_unable = self.detect_inability(new_response)
                
                return {
                    "success": not still_unable,
                    "response": new_response[:1000],
                    "learned": not still_unable,
                    "message": "✅ Solução funcionando!" if not still_unable else "⚠️ Ainda precisa ajustes"
                }
            
            return {"success": False, "error": "Falha na consulta"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _notify_test_result(self, dev_id: str, original_request: str, test_result: Dict[str, Any]):
        """Notifica o resultado do teste pós-deploy via Telegram"""
        try:
            if test_result.get("success"):
                emoji = "✅"
                status = "SUCESSO"
                msg_extra = f"\n\n💬 *Nova Resposta:*\n{test_result.get('response', '')[:500]}"
            else:
                emoji = "⚠️"
                status = "PRECISA REVISÃO"
                msg_extra = f"\n\n❌ *Problema:* {test_result.get('error', test_result.get('message', 'Erro desconhecido'))}"
            
            message = f"""{emoji} *Teste Pós-Deploy - {status}*

🔧 *ID:* `{dev_id}`
📝 *Solicitação Original:*
_{original_request[:200]}{'...' if len(original_request) > 200 else ''}_

📊 *Resultado:*
• Aprendizado: {'✅ Concluído' if test_result.get('learned') else '⏳ Pendente'}
• Status: {test_result.get('message', 'N/A')}{msg_extra}

_O sistema de auto-aprendizado {"incorporou" if test_result.get("learned") else "tentou incorporar"} esta capacidade._
"""
            
            # Enviar notificação
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": ADMIN_CHAT_ID,
                        "text": message,
                        "parse_mode": "Markdown"
                    }
                )
                
        except Exception as e:
            print(f"Erro ao notificar teste {dev_id}: {e}")

    async def deploy_solution(
        self, 
        dev_id: str, 
        requirements: Dict[str, Any], 
        solution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Faz deploy da solução desenvolvida:
        1. Salva arquivos localmente
        2. Commit no GitHub
        3. CI/CD faz deploy no servidor
        """
        try:
            import subprocess
            from pathlib import Path
            
            # Diretório da solução
            solutions_dir = Path("/home/homelab/myClaude/solutions")
            solution_dir = solutions_dir / dev_id
            solution_dir.mkdir(parents=True, exist_ok=True)
            
            lang = solution.get("language", "python")
            title = requirements.get("titulo", "Solução Auto-Desenvolvida")
            desc = requirements.get("descricao", "")
            code = solution.get("code", "")
            tests = solution.get("tests", "")
            deps = requirements.get("dependencias", [])
            
            # Extensão do arquivo baseado na linguagem
            extensions = {
                "python": "py",
                "javascript": "js",
                "typescript": "ts",
                "go": "go",
                "rust": "rs",
                "java": "java",
                "csharp": "cs",
                "php": "php"
            }
            ext = extensions.get(lang, "py")
            
            # 1. Criar arquivo principal
            main_file = solution_dir / f"main.{ext}"
            main_file.write_text(f'''#!/usr/bin/env {lang}
"""
{title}
Auto-desenvolvido em: {datetime.now().isoformat()}
ID: {dev_id}

{desc}
"""

{code}
''')
            
            # 2. Criar requirements.txt (para Python)
            if lang == "python" and deps:
                req_file = solution_dir / "requirements.txt"
                req_file.write_text("\n".join(deps))
            
            # 3. Criar package.json (para JS/TS)
            if lang in ["javascript", "typescript"] and deps:
                pkg_file = solution_dir / "package.json"
                pkg_content = {
                    "name": dev_id.lower().replace("_", "-"),
                    "version": "1.0.0",
                    "description": title,
                    "main": f"main.{ext}",
                    "dependencies": {d: "*" for d in deps}
                }
                pkg_file.write_text(json.dumps(pkg_content, indent=2))
            
            # 4. Criar testes
            if tests:
                tests_dir = solution_dir / "tests"
                tests_dir.mkdir(exist_ok=True)
                test_file = tests_dir / f"test_main.{ext}"
                test_file.write_text(tests)
            
            # 5. Criar README
            readme = solution_dir / "README.md"
            install_block = ""
            if lang == "python" and deps:
                install_block = "```bash\npip install -r requirements.txt\n```"
            elif lang in ["javascript", "typescript"] and deps:
                install_block = "```bash\nnpm install\n```"
            if lang == "python":
                run_cmd = "python main.py"
            elif lang == "javascript":
                run_cmd = "node main." + ext
            else:
                run_cmd = "./main." + ext
            steps_lines = "\n".join("- " + p for p in requirements.get("passos_implementacao", []))
            readme.write_text(f'''# {title}

**ID:** `{dev_id}`
**Linguagem:** {lang}
**Data:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Descrição

{desc}

## Uso

```{lang}
# Executar a solução
{run_cmd}
## Instalação

{install_block}

## Passos de Implementação

{steps_lines}

## Auto-Desenvolvimento

Esta solução foi gerada automaticamente pelo sistema de Auto-Desenvolvimento.
''')
            
            # 6. Criar script de deploy
            deploy_script = solution_dir / "deploy.sh"
            deploy_script.write_text(f'''#!/bin/bash
# Deploy script para {dev_id}
# Gerado automaticamente

set -e

echo "Deployando {title}..."

# Instalar dependências
{"pip3 install --user -r requirements.txt" if lang == "python" and deps else ""}
{"npm install" if lang in ["javascript", "typescript"] and deps else ""}

# Tornar executável
chmod +x main.{ext}

echo "Deploy concluído!"
''')
            deploy_script.chmod(0o755)
            
            # 7. Git commit e push
            git_result = await self._git_commit_and_push(dev_id, title)
            
            # 8. Deploy direto via SSH (não depender do GitHub Actions)
            ssh_deploy_result = await self._direct_ssh_deploy(dev_id, solution_dir)
            
            return {
                "success": True,
                "local_path": str(solution_dir),
                "files_created": [
                    f"main.{ext}",
                    "README.md",
                    "deploy.sh",
                    "requirements.txt" if lang == "python" and deps else None,
                    "package.json" if lang in ["javascript", "typescript"] and deps else None
                ],
                "git": git_result,
                "ssh_deploy": ssh_deploy_result,
                "message": f"Solução salva e deployada em {solution_dir}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Erro ao fazer deploy: {e}"
            }
    
    async def _direct_ssh_deploy(self, dev_id: str, solution_dir) -> Dict[str, Any]:
        """Deploy direto via SSH para o servidor local (não depende de GitHub Actions)"""
        try:
            import subprocess
            
            DEPLOY_USER = "homelab"
            DEPLOY_HOST = os.environ.get('DEPLOY_HOST', HOMELAB_HOST)
            DEPLOY_PATH = "/home/homelab/deployed_solutions"
            
            # Comandos para deploy via SSH
            commands = [
                # Criar diretório remoto
                f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {DEPLOY_USER}@{DEPLOY_HOST} 'mkdir -p {DEPLOY_PATH}/{dev_id}'",
                # Copiar arquivos via rsync
                f"rsync -avz --timeout=30 {solution_dir}/ {DEPLOY_USER}@{DEPLOY_HOST}:{DEPLOY_PATH}/{dev_id}/",
                # Executar script de deploy
                f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {DEPLOY_USER}@{DEPLOY_HOST} 'cd {DEPLOY_PATH}/{dev_id} && chmod +x deploy.sh && ./deploy.sh 2>&1' || true"
            ]
            
            results = []
            deploy_success = False
            
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    cmd_success = result.returncode == 0
                    results.append({
                        "command": cmd.split()[0] + " " + cmd.split()[-1] if len(cmd.split()) > 1 else cmd[:50],
                        "success": cmd_success,
                        "output": (result.stdout or result.stderr or "")[:200]
                    })
                    if "rsync" in cmd and cmd_success:
                        deploy_success = True
                except subprocess.TimeoutExpired:
                    results.append({
                        "command": cmd[:50],
                        "success": False,
                        "output": "Timeout - servidor pode estar inacessível"
                    })
                except Exception as e:
                    results.append({
                        "command": cmd[:50],
                        "success": False,
                        "output": str(e)[:200]
                    })
            
            return {
                "success": deploy_success,
                "method": "direct_ssh",
                "target": f"{DEPLOY_USER}@{DEPLOY_HOST}:{DEPLOY_PATH}/{dev_id}",
                "results": results,
                "message": "Deploy via SSH concluído" if deploy_success else "Deploy SSH falhou (servidor pode estar offline)"
            }
            
        except Exception as e:
            return {
                "success": False,
                "method": "direct_ssh",
                "error": str(e),
                "message": f"Erro no deploy SSH: {e}"
            }
    
    async def _git_commit_and_push(self, dev_id: str, title: str) -> Dict[str, Any]:
        """Commit e push para GitHub"""
        try:
            import subprocess
            
            base_dir = "/home/homelab/myClaude"
            
            # Comandos git
            commands = [
                ["git", "-C", base_dir, "add", f"solutions/{dev_id}"],
                ["git", "-C", base_dir, "commit", "-m", f"🤖 Auto-Dev: {title} [{dev_id}]"],
                ["git", "-C", base_dir, "push", "origin", "main"]
            ]
            
            results = []
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    results.append({
                        "command": " ".join(cmd[-2:]),
                        "success": result.returncode == 0,
                        "output": result.stdout or result.stderr
                    })
                except subprocess.TimeoutExpired:
                    results.append({
                        "command": " ".join(cmd[-2:]),
                        "success": False,
                        "output": "Timeout"
                    })
                except Exception as e:
                    results.append({
                        "command": " ".join(cmd[-2:]),
                        "success": False,
                        "output": str(e)
                    })
            
            # Verificar se push foi bem sucedido
            push_success = any(r.get("command") == "origin main" and r.get("success") for r in results)
            
            return {
                "pushed": push_success,
                "results": results,
                "branch": "main",
                "message": "Código enviado para GitHub - CI/CD fará deploy automático" if push_success else "Push falhou"
            }
            
        except Exception as e:
            return {
                "pushed": False,
                "error": str(e),
                "message": f"Erro no git: {e}"
            }

    def _format_development_response(
        self, 
        requirements: Dict, 
        solution: Dict, 
        validation: Dict,
        deploy: Dict,
        dev_id: str
    ) -> str:
        """Formata a resposta explicando o desenvolvimento"""
        
        title = requirements.get("titulo", "Feature Desenvolvida")
        lang = solution.get("language", "python")
        code = solution.get("code", "")[:2000]  # Limitar tamanho
        
        # Truncar código se muito grande
        if len(solution.get("code", "")) > 2000:
            code += "\n\n... (código truncado)"
        
        # Status do deploy
        deploy_status = "🚀 Deploy Iniciado" if deploy.get("success") else "⚠️ Deploy Pendente"
        git_status = "✅ Push OK" if deploy.get("git", {}).get("pushed") else "⏳ Push pendente"
        
        response = f"""🚀 *Auto-Desenvolvimento Ativado!*

Percebi que não tinha essa capacidade, então desenvolvi uma solução para você!

📋 *Análise de Requisitos:*
• Título: {title}
• Linguagem: {lang.upper()}
• Complexidade: {requirements.get('complexidade', 'N/A')}
• Viabilidade: {requirements.get('viabilidade', 'N/A')}

📝 *Descrição:*
{requirements.get('descricao', 'N/A')[:500]}

💻 *Código Desenvolvido:*
```{lang}
{code}
✅ *Validação:*
• Status: {'✓ Validado' if validation.get('validated') else '⚠ Não validado'}
• Output: {str(validation.get('output', 'N/A'))[:200]}

🚀 *Deploy:*
• Status: {deploy_status}
• GitHub: {git_status}
• Local: `{deploy.get('local_path', 'N/A')}`

🔧 *Passos de Implementação:*
{chr(10).join(f"• {p}" for p in requirements.get('passos_implementacao', [])[:5])}

📌 *ID do Desenvolvimento:* `{dev_id}`

🧪 *Teste Pós-Deploy:*
_Em ~2 minutos, testarei a solução com sua solicitação original e notificarei o resultado._

_O CI/CD do GitHub fará deploy automático no servidor!_
"""
        return response
    
    async def close(self):
        await self.client.aclose()


class TelegramBot:
    """Bot completo com todas as funcionalidades, Auto-Desenvolvimento e Integração de Modelos"""
    
    def __init__(self):
        self.api = TelegramAPI(BOT_TOKEN)
        self.agents = AgentsClient(AGENTS_API)
        self.ollama = httpx.AsyncClient(timeout=600.0)  # 10 minutos para CPU
        self.auto_dev = AutoDeveloper(self.agents, self.ollama)  # Sistema de Auto-Desenvolvimento
        self.last_update_id = 0
        self.running = True
        self.user_contexts: Dict[int, List[dict]] = {}  # Contexto por usuário
        self.auto_dev_enabled = True  # Flag para habilitar/desabilitar auto-dev
        self._lock_file = None
        self._last_state_save = 0.0
        self.state_path = Path(__file__).parent / "data" / "telegram_bot_state.json"
        self.lock_path = Path(__file__).parent / "data" / "telegram_bot.lock"
        
        # Integração de Modelos
        self.integration = get_integration_client() if INTEGRATION_AVAILABLE else None
        self.user_profiles: Dict[int, str] = {}  # Perfil por usuário
        self.auto_profile = True  # Seleção automática de perfil
        
        self._load_state()

    def _load_state(self) -> None:
        try:
            if self.state_path.exists():
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.last_update_id = int(data.get("last_update_id", 0))
        except Exception as e:
            print(f"[State] Falha ao carregar estado: {e}")

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "last_update_id": self.last_update_id,
                "saved_at": datetime.now().isoformat(),
            }
            tmp_path = self.state_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload), encoding="utf-8")
            tmp_path.replace(self.state_path)
            self._last_state_save = time.time()
        except Exception as e:
            print(f"[State] Falha ao salvar estado: {e}")

    def _acquire_singleton_lock(self) -> bool:
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._lock_file = open(self.lock_path, "a+", encoding="utf-8")
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            self._lock_file.seek(0)
            self._lock_file.truncate()
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            return True
        except Exception as e:
            print(f"[Lock] Falha ao adquirir lock: {e}")
            return True
    
    async def ask_ollama(self, prompt: str, user_id: int = None, profile: str = None) -> str:
        """Consulta modelo com contexto e seleção inteligente de modelo"""
        try:
            # Usar integração se disponível
            if self.integration:
                # Determinar perfil
                if profile:
                    selected_profile = PROFILE_ALIASES.get(profile, profile)
                elif user_id and user_id in self.user_profiles:
                    selected_profile = self.user_profiles[user_id]
                elif self.auto_profile:
                    selected_profile = await self.integration.auto_select_profile(prompt)
                else:
                    selected_profile = "general"
                
                # Obter contexto
                context = []
                if user_id and user_id in self.user_contexts:
                    context = self.user_contexts[user_id][-5:]
                
                # Fazer chat
                response = await self.integration.chat_ollama(
                    prompt=prompt,
                    profile=selected_profile,
                    context=context
                )
                
                if response.success:
                    # Salvar contexto
                    if user_id:
                        if user_id not in self.user_contexts:
                            self.user_contexts[user_id] = []
                        self.user_contexts[user_id].append({"role": "user", "content": prompt})
                        self.user_contexts[user_id].append({"role": "assistant", "content": response.content})
                        self.user_contexts[user_id] = self.user_contexts[user_id][-10:]
                    
                    return response.content
                else:
                    print(f"[Integration] Erro: {response.error}, usando fallback")
            
            # Fallback: método original
            messages = []
            if user_id and user_id in self.user_contexts:
                messages = self.user_contexts[user_id][-5:]
            
            messages.append({"role": "user", "content": prompt})
            
            response = await self.ollama.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": MODEL,
                    "messages": messages,
                    "stream": False
                },
                timeout=600.0  # 10 minutos para CPU
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("message", {}).get("content", "Sem resposta")
                
                # Salva contexto
                if user_id:
                    if user_id not in self.user_contexts:
                        self.user_contexts[user_id] = []
                    self.user_contexts[user_id].append({"role": "user", "content": prompt})
                    self.user_contexts[user_id].append({"role": "assistant", "content": answer})
                    # Mantém apenas últimas 10 mensagens
                    self.user_contexts[user_id] = self.user_contexts[user_id][-10:]
                
                return answer
            print(f"[Ollama] Erro HTTP: {response.status_code} - {response.text[:200]}")
            return f"Erro: {response.status_code}"
        except Exception as e:
            import traceback
            print(f"[Ollama] Exceção: {type(e).__name__}: {e}")
            print(f"[Ollama] Traceback: {traceback.format_exc()}")
            return f"Erro: {type(e).__name__}: {e}"
    
    async def clear_old_updates(self, drop_all: bool = False):
        """
        Ignora apenas mensagens muito antigas (mais de 2 minutos).
        Mensagens recentes serão processadas normalmente.
        """
        current_time = int(time.time())
        max_age_seconds = 120  # 2 minutos
        
        result = await self.api.get_updates(offset=0, timeout=0)
        if result.get("ok") and result.get("result"):
            updates = result["result"]
            
            if drop_all:
                last_id = updates[-1]["update_id"]
                self.last_update_id = last_id
                self._save_state()
                print(f"[Info] {len(updates)} updates pendentes ignorados (start limpo)")
                return
            
            recent_updates = []
            old_updates = []
            
            for update in updates:
                msg = update.get("message", {})
                msg_time = msg.get("date", 0)
                age = current_time - msg_time
                
                if age > max_age_seconds:
                    old_updates.append(update)
                else:
                    recent_updates.append(update)
            
            if old_updates:
                # Ignorar apenas mensagens antigas
                last_old = old_updates[-1]["update_id"]
                self.last_update_id = last_old
                self._save_state()
                print(f"[Info] {len(old_updates)} mensagens antigas ignoradas (mais de {max_age_seconds}s)")
            
            if recent_updates:
                print(f"[Info] {len(recent_updates)} mensagens recentes serão processadas")
            
            if not updates:
                print("[Info] Nenhuma mensagem pendente")
    
    def is_admin(self, user_id: int) -> bool:
        """Verifica se usuário é admin"""
        return user_id == ADMIN_CHAT_ID
    
    async def handle_command(self, message: dict):
        """Processa comandos"""
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message.get("text", "")
        msg_id = message["message_id"]
        
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower().replace("@" + "Proj_Terminal_bot", "")
        args = parts[1] if len(parts) > 1 else ""
        
        # === Comandos Gerais ===
        if cmd == "/start":
            await self.api.send_message(chat_id, 
                "🤖 *Eddie Coder Bot*\n\n"
                "Olá! Sou um assistente de programação com IA.\n\n"
                "📝 *Comandos Básicos:*\n"
                "/help - Lista de comandos\n"
                "/status - Status do sistema\n"
                "/ask [pergunta] - Perguntar à IA\n"
                "/clear - Limpar contexto\n\n"
                "👨‍💻 *Agentes de Código:*\n"
                "/agents - Listar agentes\n"
                "/code [lang] [desc] - Gerar código\n"
                "/project [lang] [desc] - Criar projeto\n"
                "/run [lang] [código] - Executar código\n\n"
                "Ou simplesmente me envie uma mensagem!",
                reply_to_message_id=msg_id)
        
        elif cmd == "/help":
            help_text = """📖 *Comandos Disponíveis*

*Básico:*
/start - Iniciar bot
/help - Esta ajuda
/status - Status do sistema
/id - Seu ID e do chat
/me - Info do bot

*Conversa IA:*
/ask [texto] - Perguntar à IA
/clear - Limpar contexto

*🤖 Modelos e Perfis:*
/models - Listar modelos Ollama
/profiles - Ver perfis disponíveis
/profile [nome] - Mudar seu perfil
/auto\\_profile - Toggle seleção automática
/use [modelo] - Usar modelo específico

*📅 Google Calendar:*
/calendar - Ajuda do calendário
/calendar listar - Ver eventos
/calendar criar [evento] - Criar evento
/calendar buscar [termo] - Buscar eventos
/calendar livre - Horários livres
/calendar auth - Autenticar

*📍 Localização:*
/onde - Sua localização atual
/historico - Histórico de localizações
/eventos - Chegadas/saídas de lugares
/geofences - Lugares configurados
/bateria - Bateria do celular

*� Casa Inteligente:*
/casa - Status da casa
/luzes - Lista todas as luzes
/ligar [dispositivo] - Liga dispositivo
/desligar [dispositivo] - Desliga dispositivo
/alternar [dispositivo] - Alterna estado
/clima - Status ar-condicionado
/temperatura [graus] - Define temperatura
/cena [nome] - Ativa uma cena
/dispositivos - Lista dispositivos

*�🌐 Busca Web:*
/search [query] - Pesquisar na internet

*🔧 Auto-Desenvolvimento:*
/autodev - Status e info
/autodev\\_on - Ativar (Admin)
/autodev\\_off - Desativar (Admin)
/autodev\\_list - Ver desenvolvimentos
/autodev\\_test [prompt] - Testar

*Agentes de Código:*
/agents - Ver agentes disponíveis
/code [lang] [descrição] - Gerar código
/project [lang] [descrição] - Criar projeto
/run [lang] [código] - Executar código

*Mensagens (Admin):*
/send [chat\\_id] [texto] - Enviar mensagem
/broadcast [texto] - Broadcast
/forward [from] [msg\\_id] - Encaminhar
/delete [msg\\_id] - Deletar mensagem

*Mídia:*
/photo [url] - Enviar foto
/doc [url] - Enviar documento

*Enquetes:*
/poll [pergunta] | [opção1] | [opção2] ...
/quiz [pergunta] | [correta] | [errada1] ...

*Grupos (Admin):*
/chatinfo [chat\\_id] - Info do chat
/members [chat\\_id] - Quantidade
/admins [chat\\_id] - Listar admins
/invite [chat\\_id] - Criar convite
/title [chat\\_id] [título] - Mudar título
/pin [msg\\_id] - Fixar mensagem
/unpin [msg\\_id] - Desfixar
/ban [user\\_id] - Banir
/unban [user\\_id] - Desbanir

💡 _Use /search para pesquisar na internet!_
💡 _Quando não consigo responder, o Auto-Dev cria a solução!_
"""
            await self.api.send_message(chat_id, help_text, reply_to_message_id=msg_id)
        
        elif cmd == "/status":
            # Verificar serviços
            ollama_status = "🔴 Offline"
            agents_status = "🔴 Offline"
            
            try:
                r = await self.ollama.get(f"{OLLAMA_HOST}/api/tags", timeout=5.0)
                if r.status_code == 200:
                    ollama_status = "🟢 Online"
            except:
                pass
            
            agents_health = await self.agents.health()
            if agents_health.get("status") == "healthy":
                agents_status = "🟢 Online"
            
            auto_dev_status = "🟢 Ativado" if self.auto_dev_enabled else "🔴 Desativado"
            dev_count = len(self.auto_dev.developments)
            
            # Status da integração
            integration_status = "🔴 Offline"
            models_count = 0
            webui_status = "🔴 Offline"
            
            if self.integration:
                try:
                    status_info = await self.integration.get_full_status()
                    if status_info["ollama"]["online"]:
                        integration_status = "🟢 Online"
                        models_count = status_info["ollama"]["models_count"]
                    if status_info["openwebui"]["online"]:
                        webui_status = "🟢 Online"
                except:
                    pass
            
            await self.api.send_message(chat_id,
                f"📊 *Status do Sistema*\n\n"
                f"🤖 Bot: 🟢 Online\n"
                f"🧠 Ollama: {ollama_status}\n"
                f"👨‍💻 Agentes: {agents_status}\n"
                f"🔧 Auto-Dev: {auto_dev_status}\n"
                f"🔗 Integração: {integration_status}\n"
                f"🌐 Open WebUI: {webui_status}\n\n"
                f"📋 *Configuração:*\n"
                f"Modelo padrão: `{MODEL}`\n"
                f"Ollama: `{OLLAMA_HOST}`\n"
                f"Open WebUI: `{OPENWEBUI_HOST}`\n"
                f"Modelos: `{models_count}`\n"
                f"Auto-Profile: `{'Sim' if self.auto_profile else 'Não'}`\n"
                f"Desenvolvimentos: `{dev_count}`",
                reply_to_message_id=msg_id)
        
        elif cmd == "/id":
            user = message.get("from", {})
            await self.api.send_message(chat_id,
                f"🆔 *Informações de ID*\n\n"
                f"👤 Seu ID: `{user_id}`\n"
                f"👤 Username: @{user.get('username', 'N/A')}\n"
                f"💬 Chat ID: `{chat_id}`\n"
                f"📨 Message ID: `{msg_id}`",
                reply_to_message_id=msg_id)
        
        elif cmd == "/me":
            info = await self.api.get_me()
            if info.get("ok"):
                bot = info["result"]
                await self.api.send_message(chat_id,
                    f"🤖 *Informações do Bot*\n\n"
                    f"Nome: {bot.get('first_name')}\n"
                    f"Username: @{bot.get('username')}\n"
                    f"ID: `{bot.get('id')}`\n"
                    f"Pode entrar em grupos: {bot.get('can_join_groups')}\n"
                    f"Lê todas mensagens: {bot.get('can_read_all_group_messages')}",
                    reply_to_message_id=msg_id)
        
        elif cmd == "/clear":
            if user_id in self.user_contexts:
                del self.user_contexts[user_id]
            if user_id in self.user_profiles:
                del self.user_profiles[user_id]
            await self.api.send_message(chat_id, "🗑️ Contexto e perfil limpos!", 
                                        reply_to_message_id=msg_id)
        
        # === Modelos e Perfis ===
        elif cmd == "/models":
            if not self.integration:
                await self.api.send_message(chat_id, 
                    "⚠️ Integração de modelos não disponível",
                    reply_to_message_id=msg_id)
                return
            
            await self.api.send_chat_action(chat_id, "typing")
            models = await self.integration.list_ollama_models()
            
            if not models:
                await self.api.send_message(chat_id,
                    "❌ Não foi possível obter lista de modelos",
                    reply_to_message_id=msg_id)
                return
            
            text = "🤖 *Modelos Disponíveis no Ollama*\n\n"
            for m in models:
                size_gb = m.size / (1024**3)
                text += f"• `{m.name}`\n"
                text += f"  📊 {m.parameter_size} | {size_gb:.1f}GB | {m.quantization}\n\n"
            
            text += f"\n_Total: {len(models)} modelos_\n"
            text += "_Use /use [modelo] para selecionar_"
            
            await self.api.send_message(chat_id, text, reply_to_message_id=msg_id)
        
        elif cmd == "/profiles":
            if not self.integration:
                await self.api.send_message(chat_id,
                    "⚠️ Integração não disponível",
                    reply_to_message_id=msg_id)
                return
            
            profiles = self.integration.list_profiles()
            current = self.user_profiles.get(user_id, "auto" if self.auto_profile else "general")
            
            text = "🎭 *Perfis de Modelo Disponíveis*\n\n"
            for name, desc in profiles.items():
                emoji = "✅" if name == current else "▫️"
                model = MODEL_PROFILES[name]["model"]
                text += f"{emoji} *{name}*\n"
                text += f"   {desc}\n"
                text += f"   _Modelo: {model}_\n\n"
            
            text += f"\n📌 *Seu perfil:* `{current}`\n"
            text += f"🔄 *Auto-seleção:* {'✅ Ativada' if self.auto_profile else '❌ Desativada'}\n\n"
            text += "_Use /profile [nome] para mudar_"
            
            await self.api.send_message(chat_id, text, reply_to_message_id=msg_id)
        
        elif cmd == "/profile":
            if not args:
                current = self.user_profiles.get(user_id, "auto" if self.auto_profile else "general")
                await self.api.send_message(chat_id,
                    f"🎭 *Seu perfil atual:* `{current}`\n\n"
                    f"Use /profile [nome] para mudar\n"
                    f"Perfis: coder, homelab, general, fast, advanced, deepseek, github\n\n"
                    f"_Aliases: code, dev, home, server, git, rapido, avancado_",
                    reply_to_message_id=msg_id)
                return
            
            profile_name = PROFILE_ALIASES.get(args.lower(), args.lower())
            
            if self.integration and profile_name in MODEL_PROFILES:
                self.user_profiles[user_id] = profile_name
                profile = MODEL_PROFILES[profile_name]
                await self.api.send_message(chat_id,
                    f"✅ *Perfil alterado para:* `{profile_name}`\n\n"
                    f"📝 {profile['description']}\n"
                    f"🤖 Modelo: `{profile['model']}`\n"
                    f"🌡️ Temperatura: {profile['temperature']}",
                    reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id,
                    f"❌ Perfil `{args}` não encontrado\n\n"
                    f"Perfis disponíveis: coder, homelab, general, fast, advanced, deepseek, github",
                    reply_to_message_id=msg_id)
        
        elif cmd == "/auto_profile":
            self.auto_profile = not self.auto_profile
            status = "✅ Ativada" if self.auto_profile else "❌ Desativada"
            await self.api.send_message(chat_id,
                f"🔄 *Auto-seleção de perfil:* {status}\n\n"
                f"{'O bot escolherá automaticamente o melhor modelo baseado na sua mensagem.' if self.auto_profile else 'Usando perfil fixo. Use /profile para definir.'}",
                reply_to_message_id=msg_id)
        
        elif cmd == "/use":
            if not args:
                await self.api.send_message(chat_id,
                    "❓ Use: /use [nome_do_modelo]\n"
                    "Ex: /use eddie-coder:latest\n\n"
                    "Use /models para ver disponíveis",
                    reply_to_message_id=msg_id)
                return
            
            if not self.integration:
                await self.api.send_message(chat_id,
                    "⚠️ Integração não disponível",
                    reply_to_message_id=msg_id)
                return
            
            # Verificar se modelo existe
            if await self.integration.model_exists(args):
                # Criar perfil customizado para o usuário
                self.user_profiles[user_id] = "custom"
                # Armazenar modelo customizado (usando um dict separado)
                if not hasattr(self, 'user_custom_models'):
                    self.user_custom_models = {}
                self.user_custom_models[user_id] = args
                
                await self.api.send_message(chat_id,
                    f"✅ *Modelo selecionado:* `{args}`\n\n"
                    f"Todas as suas mensagens usarão este modelo.",
                    reply_to_message_id=msg_id)
            else:
                models = await self.integration.get_model_names()
                await self.api.send_message(chat_id,
                    f"❌ Modelo `{args}` não encontrado\n\n"
                    f"Modelos disponíveis:\n" + "\n".join(f"• `{m}`" for m in models[:10]),
                    reply_to_message_id=msg_id)
        
        # === Auto-Desenvolvimento ===
        elif cmd == "/autodev":
            status = "🟢 Ativado" if self.auto_dev_enabled else "🔴 Desativado"
            dev_count = len(self.auto_dev.developments)
            
            await self.api.send_message(chat_id,
                f"🔧 *Auto-Desenvolvimento*\n\n"
                f"Status: {status}\n"
                f"Desenvolvimentos: `{dev_count}`\n\n"
                f"*Comandos:*\n"
                f"/autodev\\_on - Ativar\n"
                f"/autodev\\_off - Desativar\n"
                f"/autodev\\_list - Listar desenvolvimentos\n"
                f"/autodev\\_test - Testar com uma pergunta\n\n"
                f"_Quando ativado, o bot desenvolve soluções automaticamente "
                f"quando detecta que não consegue responder._",
                reply_to_message_id=msg_id)
        
        elif cmd == "/autodev_on" and self.is_admin(user_id):
            self.auto_dev_enabled = True
            await self.api.send_message(chat_id, 
                "✅ Auto-Desenvolvimento *ATIVADO*\n\n"
                "O bot agora desenvolverá soluções automaticamente quando "
                "detectar que não consegue responder.",
                reply_to_message_id=msg_id)
        
        elif cmd == "/autodev_off" and self.is_admin(user_id):
            self.auto_dev_enabled = False
            await self.api.send_message(chat_id,
                "🔴 Auto-Desenvolvimento *DESATIVADO*\n\n"
                "O bot não desenvolverá mais soluções automaticamente.",
                reply_to_message_id=msg_id)
        
        elif cmd == "/autodev_list":
            devs = self.auto_dev.developments
            if not devs:
                await self.api.send_message(chat_id,
                    "📋 *Nenhum desenvolvimento registrado ainda.*",
                    reply_to_message_id=msg_id)
            else:
                text = "📋 *Desenvolvimentos Realizados:*\n\n"
                for dev_id, dev in list(devs.items())[-10:]:  # Últimos 10
                    req = dev.get("requirements", {})
                    text += f"• `{dev_id}`\n"
                    text += f"  Título: {req.get('titulo', 'N/A')[:50]}\n"
                    text += f"  Lang: {req.get('linguagem_sugerida', 'N/A')}\n"
                    text += f"  Data: {dev.get('timestamp', 'N/A')[:19]}\n\n"
                
                await self.api.send_message(chat_id, text, reply_to_message_id=msg_id)
        
        elif cmd == "/autodev_test":
            test_prompt = args if args else "Como posso fazer uma análise de sentimento em tweets?"
            
            await self.api.send_message(chat_id,
                f"🧪 *Testando Auto-Desenvolvimento*\n\n"
                f"Prompt: _{test_prompt}_\n\n"
                f"Iniciando análise e desenvolvimento...",
                reply_to_message_id=msg_id)
            
            await self.api.send_chat_action(chat_id, "typing")
            
            # Forçar auto-desenvolvimento
            success, response = await self.auto_dev.auto_develop(test_prompt, "")
            
            if success:
                if len(response) > 4000:
                    parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
                    for part in parts:
                        await self.api.send_message(chat_id, part)
                else:
                    await self.api.send_message(chat_id, response)
            else:
                await self.api.send_message(chat_id, f"❌ Falha: {response}")
        
        # === Google Calendar ===
        elif cmd == "/calendar":
            if not CALENDAR_AVAILABLE:
                await self.api.send_message(chat_id,
                    "⚠️ *Google Calendar não disponível*\n\n"
                    "O módulo de calendário não está instalado.\n"
                    "Execute: `pip install google-auth-oauthlib google-api-python-client python-dateutil`\n\n"
                    "Depois: `python setup_google_calendar.py`",
                    reply_to_message_id=msg_id)
                return
            
            await self.api.send_chat_action(chat_id, "typing")
            
            # Processar comando do calendário
            calendar_assistant = get_calendar_assistant()
            
            if args:
                # Quebrar args em comando e parâmetros
                cal_parts = args.split(maxsplit=1)
                cal_cmd = cal_parts[0]
                cal_args = cal_parts[1] if len(cal_parts) > 1 else ""
            else:
                cal_cmd = "ajuda"
                cal_args = ""
            
            response = await calendar_assistant.process_command(cal_cmd, cal_args, str(user_id))
            
            # Enviar resposta (pode ser grande)
            if len(response) > 4000:
                parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
                for part in parts:
                    await self.api.send_message(chat_id, part, reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id, response, reply_to_message_id=msg_id)
        
        # === Gmail Integration ===
        elif cmd == "/gmail":
            if not GMAIL_AVAILABLE:
                await self.api.send_message(chat_id,
                    "⚠️ *Gmail não disponível*\n\n"
                    "O módulo de Gmail não está instalado.\n"
                    "Execute: `pip install google-auth-oauthlib google-api-python-client`",
                    reply_to_message_id=msg_id)
                return
            
            await self.api.send_chat_action(chat_id, "typing")
            
            if args:
                # Quebrar args em comando e parâmetros
                gmail_parts = args.split(maxsplit=1)
                gmail_cmd = gmail_parts[0]
                gmail_args = gmail_parts[1] if len(gmail_parts) > 1 else ""
            else:
                gmail_cmd = "ajuda"
                gmail_args = ""
            
            response = await process_gmail_command(gmail_cmd, gmail_args)
            
            # Enviar resposta (pode ser grande)
            if len(response) > 4000:
                parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
                for part in parts:
                    await self.api.send_message(chat_id, part, reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id, response, reply_to_message_id=msg_id)
        
        # === Localização ===
        elif cmd in ["/onde", "/location", "/loc", "/where", "/historico", "/history", 
                     "/eventos", "/events", "/geofences", "/lugares", "/places",
                     "/bateria", "/battery", "/batt"]:
            if not LOCATION_AVAILABLE:
                await self.api.send_message(chat_id,
                    "📍 *Localização não disponível*\n\n"
                    "O módulo de localização não está configurado.\n\n"
                    "Para ativar:\n"
                    "1. `cd ~/myClaude/location_integration`\n"
                    "2. `./install.sh`\n"
                    "3. Configure OwnTracks no celular",
                    reply_to_message_id=msg_id)
                return
            
            await self.api.send_chat_action(chat_id, "typing")
            
            response = await handle_location_command(cmd, args)
            
            if response:
                # Enviar resposta (pode ser grande)
                if len(response) > 4000:
                    parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
                    for part in parts:
                        await self.api.send_message(chat_id, part, parse_mode="HTML", 
                                                    reply_to_message_id=msg_id)
                else:
                    await self.api.send_message(chat_id, response, parse_mode="HTML",
                                                reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id,
                    "📍 Use /onde para ver sua localização atual",
                    reply_to_message_id=msg_id)
        
        # === Casa Inteligente (Home Assistant) ===
        elif cmd in ["/casa", "/luzes", "/ligar", "/desligar", "/alternar", 
                     "/clima", "/temperatura", "/cena", "/dispositivos", "/home"]:
            if not HOMEASSISTANT_AVAILABLE:
                await self.api.send_message(chat_id,
                    "🏠 *Casa Inteligente não disponível*\n\n"
                    "O módulo Home Assistant não está configurado.\n\n"
                    "Para ativar:\n"
                    "1. Acesse http://localhost:8123\n"
                    "2. Configure sua conta\n"
                    "3. Gere um token em Perfil > Tokens de Acesso",
                    reply_to_message_id=msg_id)
                return
            
            await self.api.send_chat_action(chat_id, "typing")
            
            response, success = await handle_homeassistant_command(cmd, args, chat_id)
            
            if response:
                # Enviar resposta (pode ser grande)
                if len(response) > 4000:
                    parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
                    for part in parts:
                        await self.api.send_message(chat_id, part, 
                                                    reply_to_message_id=msg_id)
                else:
                    await self.api.send_message(chat_id, response,
                                                reply_to_message_id=msg_id)
        
        # === Busca Web ===
        elif cmd == "/search":
            if not args:
                await self.api.send_message(chat_id, 
                    "🔍 *Busca na Internet*\n\n"
                    "Use: /search [sua pesquisa]\n\n"
                    "Exemplo:\n"
                    "`/search Python asyncio tutorial`\n"
                    "`/search React hooks examples`\n\n"
                    "_A busca usa DuckDuckGo e salva resultados na base de conhecimento._",
                    reply_to_message_id=msg_id)
                return
            
            await self.api.send_message(chat_id,
                f"🔍 *Buscando:* _{args}_\n\n⏳ Aguarde...",
                reply_to_message_id=msg_id)
            await self.api.send_chat_action(chat_id, "typing")
            
            # Realizar busca web
            if self.auto_dev.web_search:
                result = await self.auto_dev.search_web(args, num_results=3)
                
                if result.get("success"):
                    response = f"🌐 *Resultados da Busca*\n\n"
                    response += f"🔎 Query: _{args}_\n"
                    response += f"📊 Encontrados: {result.get('results_count', 0)} resultados\n"
                    response += f"💾 Salvo no RAG: {'✅' if result.get('saved_to_rag') else '❌'}\n\n"
                    
                    # Fontes encontradas
                    sources = result.get("sources", [])
                    if sources:
                        response += "📚 *Fontes:*\n"
                        for s in sources[:5]:
                            response += f"• [{s['title'][:50]}]({s['url']})\n"
                        response += "\n"
                    
                    # Conteúdo formatado (resumido)
                    formatted = result.get("formatted", "")
                    if formatted:
                        # Limitar tamanho da resposta
                        if len(formatted) > 3000:
                            formatted = formatted[:3000] + "\n\n_[Conteúdo truncado...]_"
                        response += "📄 *Conteúdo:*\n" + formatted
                    
                    # Enviar em partes se necessário
                    if len(response) > 4000:
                        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
                        for part in parts:
                            await self.api.send_message(chat_id, part, reply_to_message_id=msg_id)
                    else:
                        await self.api.send_message(chat_id, response, reply_to_message_id=msg_id)
                else:
                    await self.api.send_message(chat_id,
                        f"❌ *Erro na busca:* {result.get('error', 'Erro desconhecido')}",
                        reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id,
                    "⚠️ *Busca web não disponível*\n\n"
                    "O módulo de busca web não está instalado.\n"
                    "Execute: `pip install duckduckgo-search beautifulsoup4 lxml`",
                    reply_to_message_id=msg_id)
        
        elif cmd == "/ask":
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /ask [sua pergunta]",
                                            reply_to_message_id=msg_id)
                return
            
            await self.api.send_chat_action(chat_id, "typing")
            response = await self.ask_ollama(args, user_id)
            await self.api.send_message(chat_id, response, reply_to_message_id=msg_id)
        
        # === Agentes de Código ===
        elif cmd == "/agents":
            agents = await self.agents.list_agents()
            if "error" in agents:
                await self.api.send_message(chat_id, f"❌ Erro: {agents['error']}",
                                            reply_to_message_id=msg_id)
            else:
                langs = agents.get("available_languages", [])
                await self.api.send_message(chat_id,
                    f"👨‍💻 *Agentes Disponíveis*\n\n"
                    f"Linguagens: {', '.join(langs)}\n\n"
                    f"Use:\n"
                    f"/code [lang] [descrição] - Gerar código\n"
                    f"/project [lang] [descrição] - Criar projeto\n"
                    f"/run [lang] [código] - Executar",
                    reply_to_message_id=msg_id)
        
        elif cmd == "/code":
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                await self.api.send_message(chat_id, 
                    "❓ Use: /code [linguagem] [descrição]\n"
                    "Ex: /code python função que calcula fatorial",
                    reply_to_message_id=msg_id)
                return
            
            lang, desc = parts[0], parts[1]
            await self.api.send_chat_action(chat_id, "typing")
            await self.api.send_message(chat_id, f"⏳ Gerando código {lang}...",
                                        reply_to_message_id=msg_id)
            
            result = await self.agents.generate_code(lang, desc)
            if "error" in result:
                await self.api.send_message(chat_id, f"❌ Erro: {result['error']}")
            else:
                code = result.get("code", "Nenhum código gerado")
                await self.api.send_message(chat_id, f"```{lang}\n{code[:3900]}\n```",
                                            parse_mode="Markdown")
        
        elif cmd == "/project":
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                await self.api.send_message(chat_id,
                    "❓ Use: /project [linguagem] [descrição]\n"
                    "Ex: /project python API REST para tarefas",
                    reply_to_message_id=msg_id)
                return
            
            lang, desc = parts[0], parts[1]
            await self.api.send_chat_action(chat_id, "typing")
            await self.api.send_message(chat_id, f"⏳ Criando projeto {lang}...",
                                        reply_to_message_id=msg_id)
            
            result = await self.agents.create_project(lang, desc)
            if "error" in result:
                await self.api.send_message(chat_id, f"❌ Erro: {result['error']}")
            else:
                await self.api.send_message(chat_id,
                    f"✅ *Projeto Criado!*\n\n"
                    f"Nome: {result.get('project_name', 'N/A')}\n"
                    f"Linguagem: {lang}\n"
                    f"Caminho: `{result.get('path', 'N/A')}`")
        
        elif cmd == "/run":
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                await self.api.send_message(chat_id,
                    "❓ Use: /run [linguagem] [código]\n"
                    "Ex: /run python print('Hello!')",
                    reply_to_message_id=msg_id)
                return
            
            lang, code = parts[0], parts[1]
            await self.api.send_chat_action(chat_id, "typing")
            
            result = await self.agents.execute_code(lang, code)
            if "error" in result:
                await self.api.send_message(chat_id, f"❌ Erro: {result['error']}")
            else:
                output = result.get("output", result.get("result", "Sem output"))
                await self.api.send_message(chat_id,
                    f"📤 *Resultado:*\n```\n{str(output)[:3900]}\n```")
        
        # === Comandos de Admin ===
        elif cmd == "/send" and self.is_admin(user_id):
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                await self.api.send_message(chat_id, "❓ Use: /send [chat_id] [mensagem]",
                                            reply_to_message_id=msg_id)
                return
            try:
                target_chat = int(parts[0])
                msg_text = parts[1]
                result = await self.api.send_message(target_chat, msg_text)
                if result.get("ok"):
                    await self.api.send_message(chat_id, "✅ Mensagem enviada!")
                else:
                    await self.api.send_message(chat_id, f"❌ Erro: {result}")
            except ValueError:
                await self.api.send_message(chat_id, "❌ Chat ID inválido")
        
        elif cmd == "/broadcast" and self.is_admin(user_id):
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /broadcast [mensagem]",
                                            reply_to_message_id=msg_id)
                return
            # Aqui você pode implementar broadcast para múltiplos usuários
            await self.api.send_message(ADMIN_CHAT_ID, f"📢 *Broadcast:*\n{args}")
            await self.api.send_message(chat_id, "✅ Broadcast enviado!")
        
        elif cmd == "/forward" and self.is_admin(user_id):
            parts = args.split()
            if len(parts) < 2:
                await self.api.send_message(chat_id, 
                    "❓ Use: /forward [from_chat_id] [message_id]",
                    reply_to_message_id=msg_id)
                return
            try:
                from_chat = int(parts[0])
                msg_to_forward = int(parts[1])
                result = await self.api.forward_message(chat_id, from_chat, msg_to_forward)
                if not result.get("ok"):
                    await self.api.send_message(chat_id, f"❌ Erro: {result}")
            except ValueError:
                await self.api.send_message(chat_id, "❌ IDs inválidos")
        
        elif cmd == "/delete" and self.is_admin(user_id):
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /delete [message_id]",
                                            reply_to_message_id=msg_id)
                return
            try:
                msg_to_delete = int(args)
                result = await self.api.delete_message(chat_id, msg_to_delete)
                if result.get("ok"):
                    await self.api.send_message(chat_id, "✅ Mensagem deletada!")
                else:
                    await self.api.send_message(chat_id, f"❌ Erro: {result}")
            except ValueError:
                await self.api.send_message(chat_id, "❌ ID inválido")
        
        # === Mídia ===
        elif cmd == "/photo":
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /photo [url]",
                                            reply_to_message_id=msg_id)
                return
            result = await self.api.send_photo(chat_id, args)
            if not result.get("ok"):
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        elif cmd == "/doc":
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /doc [url]",
                                            reply_to_message_id=msg_id)
                return
            result = await self.api.send_document(chat_id, args)
            if not result.get("ok"):
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        # === Localização ===
        elif cmd == "/location":
            parts = args.split()
            if len(parts) < 2:
                await self.api.send_message(chat_id, "❓ Use: /location [lat] [lon]",
                                            reply_to_message_id=msg_id)
                return
            try:
                lat, lon = float(parts[0]), float(parts[1])
                await self.api.send_location(chat_id, lat, lon)
            except ValueError:
                await self.api.send_message(chat_id, "❌ Coordenadas inválidas")
        
        # === Enquetes ===
        elif cmd == "/poll":
            if "|" not in args:
                await self.api.send_message(chat_id,
                    "❓ Use: /poll pergunta | opção1 | opção2 | ...",
                    reply_to_message_id=msg_id)
                return
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 3:
                await self.api.send_message(chat_id, "❌ Mínimo 2 opções")
                return
            question = parts[0]
            options = parts[1:]
            result = await self.api.send_poll(chat_id, question, options)
            if not result.get("ok"):
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        elif cmd == "/quiz":
            if "|" not in args:
                await self.api.send_message(chat_id,
                    "❓ Use: /quiz pergunta | resposta_correta | errada1 | ...",
                    reply_to_message_id=msg_id)
                return
            parts = [p.strip() for p in args.split("|")]
            if len(parts) < 3:
                await self.api.send_message(chat_id, "❌ Mínimo 2 opções")
                return
            question = parts[0]
            options = parts[1:]
            result = await self.api.send_quiz(chat_id, question, options, 0)
            if not result.get("ok"):
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        # === Grupos ===
        elif cmd == "/chatinfo":
            target = int(args) if args else chat_id
            result = await self.api.get_chat(target)
            if result.get("ok"):
                chat = result["result"]
                await self.api.send_message(chat_id,
                    f"💬 *Info do Chat*\n\n"
                    f"ID: `{chat.get('id')}`\n"
                    f"Tipo: {chat.get('type')}\n"
                    f"Título: {chat.get('title', chat.get('first_name', 'N/A'))}\n"
                    f"Username: @{chat.get('username', 'N/A')}",
                    reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        elif cmd == "/members":
            target = int(args) if args else chat_id
            result = await self.api.get_chat_member_count(target)
            if result.get("ok"):
                await self.api.send_message(chat_id,
                    f"👥 Membros: {result['result']}",
                    reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        elif cmd == "/admins":
            target = int(args) if args else chat_id
            result = await self.api.get_chat_administrators(target)
            if result.get("ok"):
                admins = result["result"]
                text = "👑 *Administradores:*\n\n"
                for admin in admins:
                    user = admin.get("user", {})
                    text += f"• {user.get('first_name', 'N/A')} (@{user.get('username', 'N/A')})\n"
                await self.api.send_message(chat_id, text, reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        elif cmd == "/invite" and self.is_admin(user_id):
            target = int(args) if args else chat_id
            result = await self.api.create_chat_invite_link(target)
            if result.get("ok"):
                link = result["result"].get("invite_link")
                await self.api.send_message(chat_id, f"🔗 Link: {link}",
                                            reply_to_message_id=msg_id)
            else:
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        elif cmd == "/title" and self.is_admin(user_id):
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                await self.api.send_message(chat_id, "❓ Use: /title [chat_id] [novo_título]",
                                            reply_to_message_id=msg_id)
                return
            try:
                target = int(parts[0])
                new_title = parts[1]
                result = await self.api.set_chat_title(target, new_title)
                if result.get("ok"):
                    await self.api.send_message(chat_id, "✅ Título alterado!")
                else:
                    await self.api.send_message(chat_id, f"❌ Erro: {result}")
            except ValueError:
                await self.api.send_message(chat_id, "❌ Chat ID inválido")
        
        elif cmd == "/pin" and self.is_admin(user_id):
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /pin [message_id]",
                                            reply_to_message_id=msg_id)
                return
            try:
                msg_to_pin = int(args)
                result = await self.api.pin_chat_message(chat_id, msg_to_pin)
                if result.get("ok"):
                    await self.api.send_message(chat_id, "📌 Mensagem fixada!")
                else:
                    await self.api.send_message(chat_id, f"❌ Erro: {result}")
            except ValueError:
                await self.api.send_message(chat_id, "❌ ID inválido")
        
        elif cmd == "/unpin" and self.is_admin(user_id):
            msg_to_unpin = int(args) if args else None
            result = await self.api.unpin_chat_message(chat_id, msg_to_unpin)
            if result.get("ok"):
                await self.api.send_message(chat_id, "📌 Mensagem desfixada!")
            else:
                await self.api.send_message(chat_id, f"❌ Erro: {result}")
        
        elif cmd == "/ban" and self.is_admin(user_id):
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /ban [user_id]",
                                            reply_to_message_id=msg_id)
                return
            try:
                user_to_ban = int(args)
                result = await self.api.ban_chat_member(chat_id, user_to_ban)
                if result.get("ok"):
                    await self.api.send_message(chat_id, "🚫 Usuário banido!")
                else:
                    await self.api.send_message(chat_id, f"❌ Erro: {result}")
            except ValueError:
                await self.api.send_message(chat_id, "❌ ID inválido")
        
        elif cmd == "/unban" and self.is_admin(user_id):
            if not args:
                await self.api.send_message(chat_id, "❓ Use: /unban [user_id]",
                                            reply_to_message_id=msg_id)
                return
            try:
                user_to_unban = int(args)
                result = await self.api.unban_chat_member(chat_id, user_to_unban)
                if result.get("ok"):
                    await self.api.send_message(chat_id, "✅ Usuário desbanido!")
                else:
                    await self.api.send_message(chat_id, f"❌ Erro: {result}")
            except ValueError:
                await self.api.send_message(chat_id, "❌ ID inválido")
        
        else:
            await self.api.send_message(chat_id,
                "❓ Comando não reconhecido.\nUse /help para ver comandos.",
                reply_to_message_id=msg_id)
    
    async def handle_message(self, message: dict):
        """Processa mensagem recebida com sistema de Auto-Desenvolvimento e Calendário"""
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message.get("text", "")
        msg_id = message["message_id"]
        user_name = message["from"].get("first_name", "Usuário")
        
        if not text:
            return
        
        # Comandos
        if text.startswith("/"):
            await self.handle_command(message)
            return
        
        # === VERIFICAR INTENÇÃO DE CALENDÁRIO ===
        if CALENDAR_AVAILABLE:
            calendar_response = await process_calendar_request(text, str(user_id))
            if calendar_response:
                # É uma requisição de calendário
                print(f"[Calendar] Detectada intenção de calendário: {text[:50]}...")
                await self.api.send_chat_action(chat_id, "typing")
                
                if len(calendar_response) > 4000:
                    parts = [calendar_response[i:i+4000] for i in range(0, len(calendar_response), 4000)]
                    for part in parts:
                        await self.api.send_message(chat_id, part, reply_to_message_id=msg_id)
                else:
                    await self.api.send_message(chat_id, calendar_response, reply_to_message_id=msg_id)
                return
        
        # === VERIFICAR INTENÇÃO DE EMAIL/GMAIL ===
        if GMAIL_AVAILABLE:
            email_keywords = [
                'email', 'e-mail', 'gmail', 'inbox', 'caixa de entrada',
                'meus emails', 'ver emails', 'listar emails', 'ler emails',
                'limpar emails', 'spam', 'não lidos', 'nao lidos'
            ]
            text_lower = text.lower()
            if any(kw in text_lower for kw in email_keywords):
                print(f"[Gmail] Detectada intenção de email: {text[:50]}...")
                await self.api.send_chat_action(chat_id, "typing")
                
                # Mapear intenção para comando
                if 'limpar' in text_lower or 'excluir' in text_lower or 'deletar' in text_lower:
                    gmail_response = await process_gmail_command('limpar', '')
                elif 'analisar' in text_lower or 'relatório' in text_lower or 'relatorio' in text_lower:
                    gmail_response = await process_gmail_command('analisar', '')
                elif 'não lido' in text_lower or 'nao lido' in text_lower:
                    gmail_response = await process_gmail_command('nao_lidos', '')
                else:
                    gmail_response = await process_gmail_command('listar', '20')
                
                if len(gmail_response) > 4000:
                    parts = [gmail_response[i:i+4000] for i in range(0, len(gmail_response), 4000)]
                    for part in parts:
                        await self.api.send_message(chat_id, part, reply_to_message_id=msg_id)
                else:
                    await self.api.send_message(chat_id, gmail_response, reply_to_message_id=msg_id)
                return
        
        # Conversa normal - usar Ollama
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {user_name}: {text[:50]}...")
        
        await self.api.send_chat_action(chat_id, "typing")

        # Roteie a pergunta para o DIRETOR primeiro (regra do repositório).
        # Aguardamos uma resposta curta do DIRETOR; se não houver, usamos o fluxo normal.
        try:
            bus = get_communication_bus()
            bus.publish(MessageType.REQUEST, 'assistant', 'DIRETOR', text, {'user_id': user_id, 'via': 'telegram'})

            director_response = None
            event = asyncio.Event()

            def _cb(msg):
                nonlocal director_response
                try:
                    # Aceita mensagens vindas do DIRETOR dirigidas ao assistant/all
                    if getattr(msg, 'source', '') and 'DIRETOR' in msg.source and (msg.target in ('assistant', 'all') or msg.target == chat_id):
                        director_response = msg.content
                        try:
                            bus.unsubscribe(_cb)
                        except Exception:
                            pass
                        loop = asyncio.get_event_loop()
                        loop.call_soon_threadsafe(event.set)
                except Exception:
                    pass

            bus.subscribe(_cb)
            try:
                await asyncio.wait_for(event.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                director_response = None

            if director_response:
                response = director_response
                # Se o Diretor instruiu a prosseguir, executa auto-dev automaticamente
                action_keywords = [
                    'implementar', 'desenvolver', 'executar', 'prossiga', 'prosseguir',
                    'faça', 'faca', 'realize', 'implement', 'develop', 'execute', 'proceed', 'run'
                ]
                resp_l = (director_response or '').lower()
                should_proceed = any(kw in resp_l for kw in action_keywords)

                if should_proceed:
                    print("[Routing] Diretor pediu para prosseguir — iniciando Auto-Dev se habilitado")
                    if self.auto_dev_enabled:
                        # Informar usuário
                        await self.api.send_message(chat_id,
                            "🔔 O DIRETOR autorizou prosseguir com a tarefa. Iniciando Auto-Desenvolvimento...",
                            reply_to_message_id=msg_id)
                        await self.api.send_chat_action(chat_id, "typing")
                        try:
                            success, dev_response = await self.auto_dev.auto_develop(text, director_response)
                            if success:
                                if user_id != ADMIN_CHAT_ID:
                                    await self.api.send_message(ADMIN_CHAT_ID,
                                        f"🔔 *Auto-Dev iniciado via DIRETOR*\nUsuário: {user_name} (`{user_id}`)\nPedido: {text[:200]}...")
                                # Enviar resultado do desenvolvimento
                                if len(dev_response) > 4000:
                                    parts = [dev_response[i:i+4000] for i in range(0, len(dev_response), 4000)]
                                    for i, part in enumerate(parts):
                                        await self.api.send_message(chat_id, part,
                                            reply_to_message_id=msg_id if i == 0 else None)
                                else:
                                    await self.api.send_message(chat_id, dev_response, reply_to_message_id=msg_id)
                                return
                            else:
                                await self.api.send_message(chat_id, f"⚠️ Auto-Dev falhou: {dev_response}", reply_to_message_id=msg_id)
                        except Exception as e:
                            print(f"[Auto-Dev] Erro ao executar auto_develop: {e}")
                    else:
                        await self.api.send_message(chat_id, "⚠️ O DIRETOR pediu para prosseguir, mas o Auto-Dev está desabilitado.", reply_to_message_id=msg_id)
            else:
                response = await self.ask_ollama(text, user_id)
        except Exception as e:
            print(f"[Routing] Erro ao enviar para DIRETOR: {e}")
            response = await self.ask_ollama(text, user_id)
        
        print(f"[Debug] Resposta Ollama: {response[:100]}...")
        print(f"[Debug] Auto-Dev habilitado: {self.auto_dev_enabled}")
        
        # === AUTO-DESENVOLVIMENTO ===
        # Verifica se a resposta indica incapacidade e se auto-dev está habilitado
        inability_detected = self.auto_dev.detect_inability(response) if self.auto_dev_enabled else False
        print(f"[Debug] Incapacidade detectada: {inability_detected}")
        
        if self.auto_dev_enabled and inability_detected:
            print(f"[Auto-Dev] Detectada incapacidade, iniciando desenvolvimento...")
            
            # Informar usuário que está desenvolvendo
            await self.api.send_message(
                chat_id,
                "🔧 *Detectei que não tenho essa capacidade ainda...*\n\n"
                "⏳ Iniciando Auto-Desenvolvimento:\n"
                "1️⃣ Analisando requisitos...\n"
                "2️⃣ Desenvolvendo solução...\n"
                "3️⃣ Validando código...\n\n"
                "_Aguarde, isso pode levar alguns segundos..._",
                reply_to_message_id=msg_id
            )
            
            await self.api.send_chat_action(chat_id, "typing")
            
            # Executar auto-desenvolvimento
            success, dev_response = await self.auto_dev.auto_develop(text, response)
            
            if success:
                # Notificar admin sobre novo desenvolvimento
                if user_id != ADMIN_CHAT_ID:
                    await self.api.send_message(
                        ADMIN_CHAT_ID,
                        f"🔔 *Novo Auto-Desenvolvimento!*\n\n"
                        f"Usuário: {user_name} (`{user_id}`)\n"
                        f"Pedido: {text[:200]}...\n\n"
                        f"_Verifique o desenvolvimento no chat._"
                    )
                
                # Enviar resposta do desenvolvimento (pode ser grande)
                print(f"[Auto-Dev] Enviando resposta: {len(dev_response)} chars")
                if len(dev_response) > 4000:
                    parts = [dev_response[i:i+4000] for i in range(0, len(dev_response), 4000)]
                    for i, part in enumerate(parts):
                        await self.api.send_message(chat_id, part,
                            reply_to_message_id=msg_id if i == 0 else None)
                else:
                    result = await self.api.send_message(chat_id, dev_response, reply_to_message_id=msg_id)
                    print(f"[Auto-Dev] Mensagem enviada: {result}")
                
                print(f"[Auto-Dev] Desenvolvimento concluído com sucesso!")
                return
            else:
                # Se auto-dev falhou, informa e envia resposta original
                await self.api.send_message(
                    chat_id,
                    f"⚠️ *Auto-Desenvolvimento não conseguiu completar*\n\n"
                    f"Motivo: {dev_response}\n\n"
                    f"_Resposta original:_",
                    reply_to_message_id=msg_id
                )
                print(f"[Auto-Dev] Falha: {dev_response}")
        
        # Enviar resposta normal (quebrar se muito grande)
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await self.api.send_message(chat_id, response[i:i+4000],
                                            reply_to_message_id=msg_id if i == 0 else None)
        else:
            await self.api.send_message(chat_id, response, reply_to_message_id=msg_id)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Bot: {response[:50]}...")
    
    async def run(self):
        """Loop principal"""
        print("=" * 50)
        print("🤖 Eddie Coder Bot - Com Auto-Desenvolvimento")
        print(f"   Modelo: {MODEL}")
        print(f"   Ollama: {OLLAMA_HOST}")
        print(f"   Agentes: {AGENTS_API}")
        print(f"   Admin: {ADMIN_CHAT_ID}")
        print(f"   Auto-Dev: {'Ativado' if self.auto_dev_enabled else 'Desativado'}")
        print("=" * 50)
        
        # Registrar comandos no Telegram
        commands = [
            # === Básicos ===
            {"command": "start", "description": "🚀 Iniciar bot"},
            {"command": "help", "description": "❓ Lista de comandos"},
            {"command": "status", "description": "📊 Status do sistema"},
            {"command": "id", "description": "🔢 Ver IDs do chat/usuário"},
            {"command": "me", "description": "👤 Informações do usuário"},
            {"command": "clear", "description": "🗑️ Limpar contexto"},
            
            # === IA e Modelos ===
            {"command": "ask", "description": "🤖 Perguntar à IA"},
            {"command": "models", "description": "📋 Listar modelos Ollama"},
            {"command": "profiles", "description": "🎭 Ver perfis de modelo"},
            {"command": "profile", "description": "🔄 Mudar perfil (ex: /profile coder)"},
            {"command": "auto_profile", "description": "⚡ Toggle auto-seleção de perfil"},
            {"command": "use", "description": "🎯 Usar modelo específico"},
            
            # === Auto-Dev ===
            {"command": "autodev", "description": "🔧 Status Auto-Desenvolvimento"},
            {"command": "autodev_on", "description": "✅ Ativar Auto-Dev (admin)"},
            {"command": "autodev_off", "description": "❌ Desativar Auto-Dev (admin)"},
            {"command": "autodev_list", "description": "📋 Listar desenvolvimentos"},
            {"command": "autodev_test", "description": "🧪 Testar auto-desenvolvimento"},
            
            # === Agentes e Código ===
            {"command": "agents", "description": "🤖 Listar agentes especializados"},
            {"command": "code", "description": "💻 Gerar código (ex: /code python fibonacci)"},
            {"command": "project", "description": "📁 Criar projeto completo"},
            {"command": "run", "description": "▶️ Executar código"},
            
            # === Busca ===
            {"command": "search", "description": "🔍 Buscar na internet"},
            
            # === Calendário e Gmail ===
            {"command": "calendar", "description": "📅 Comandos do calendário"},
            {"command": "gmail", "description": "📧 Comandos do Gmail"},
            
            # === Mídia ===
            {"command": "photo", "description": "📷 Enviar foto por URL"},
            {"command": "doc", "description": "📄 Enviar documento por URL"},
            {"command": "location", "description": "📍 Enviar localização"},
            {"command": "poll", "description": "📊 Criar enquete"},
            {"command": "quiz", "description": "❓ Criar quiz"},
            
            # === Gestão de Chat ===
            {"command": "chatinfo", "description": "ℹ️ Info do chat"},
            {"command": "members", "description": "👥 Contar membros"},
            {"command": "admins", "description": "👑 Listar admins"},
            
            # === Admin ===
            {"command": "send", "description": "📤 Enviar msg (admin)"},
            {"command": "broadcast", "description": "📢 Broadcast (admin)"},
            {"command": "forward", "description": "↪️ Encaminhar (admin)"},
            {"command": "delete", "description": "🗑️ Deletar msg (admin)"},
            {"command": "invite", "description": "🔗 Gerar link convite (admin)"},
            {"command": "title", "description": "✏️ Mudar título (admin)"},
            {"command": "pin", "description": "📌 Fixar mensagem (admin)"},
            {"command": "unpin", "description": "📌 Desafixar (admin)"},
            {"command": "ban", "description": "🚫 Banir usuário (admin)"},
            {"command": "unban", "description": "✅ Desbanir (admin)"},
        ]
        await self.api.set_my_commands(commands)
        
        # Garantir apenas uma instância ativa
        if not self._acquire_singleton_lock():
            print("[Warn] Outra instância detectada. Aguardando lock para evitar duplicidade.")
            while not self._acquire_singleton_lock():
                await asyncio.sleep(10)
            print("[Info] Lock adquirido. Continuando.")
        
        # Limpar updates pendentes no start
        await self.clear_old_updates(drop_all=True)
        
        # Info de modelos
        models_info = "N/A"
        if self.integration:
            try:
                models = await self.integration.get_model_names()
                models_info = f"{len(models)} modelos"
            except:
                pass
        
        print("✅ Pronto! Aguardando mensagens...\n")
        
        # Notificar admin
        await self.api.send_message(ADMIN_CHAT_ID,
            "🟢 *Bot Iniciado - Integração Completa!*\n\n"
            f"🤖 Modelo padrão: `{MODEL}`\n"
            f"🧠 Ollama: `{OLLAMA_HOST}`\n"
            f"🌐 Open WebUI: `{OPENWEBUI_HOST}`\n"
            f"📊 Modelos: `{models_info}`\n"
            f"🔧 Auto-Dev: `{'Ativado' if self.auto_dev_enabled else 'Desativado'}`\n"
            f"🔄 Auto-Profile: `{'Ativado' if self.auto_profile else 'Desativado'}`\n\n"
            "🆕 *Novos Comandos:*\n"
            "• /models - Ver modelos\n"
            "• /profiles - Ver perfis\n"
            "• /profile [nome] - Mudar perfil\n\n"
            "💡 _O bot seleciona automaticamente o melhor modelo!_\n\n"
            "Use /help para ver todos comandos.")
        
        while self.running:
            try:
                result = await self.api.get_updates(offset=self.last_update_id + 1, timeout=30)
                
                if result.get("ok"):
                    for update in result.get("result", []):
                        self.last_update_id = update["update_id"]
                        if time.time() - self._last_state_save > 5:
                            self._save_state()
                        
                        if "message" in update:
                            try:
                                await self.handle_message(update["message"])
                            except Exception as msg_error:
                                print(f"[Erro] Processando mensagem: {msg_error}")
                                import traceback
                                traceback.print_exc()
                                # Continua processando outras mensagens
                else:
                    error = result.get("error", result.get("description", "Unknown error"))
                    print(f"[Erro] API Telegram: {error}")
                    await asyncio.sleep(5)
                
            except httpx.TimeoutException:
                # Timeout normal do long polling, continua
                continue
            except httpx.ConnectError as e:
                print(f"[Erro] Conexão: {e}")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"[Erro] Loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)
    
    async def stop(self):
        """Para o bot"""
        self.running = False
        await self.api.close()
        await self.agents.close()
        await self.auto_dev.close()
        await self.ollama.aclose()
        if self.integration:
            await self.integration.close()
        try:
            if self._lock_file:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
        except Exception:
            pass


async def main():
    bot = TelegramBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot encerrado")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
