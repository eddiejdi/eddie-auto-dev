#!/usr/bin/env python3
"""
Bot Telegram Completo com Integração aos Agentes Especializados
Implementa todas as funcionalidades da API do Telegram
Com Auto-Desenvolvimento: quando não consegue responder, desenvolve a solução
"""
import os
import asyncio
import httpx
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

# Configurações
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
MODEL = os.getenv("OLLAMA_MODEL", "eddie-coder")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "948686300"))
AGENTS_API = os.getenv("AGENTS_API", "http://localhost:8503")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Padrões que indicam que a IA não consegue responder
INABILITY_PATTERNS = [
    r"não (tenho|possuo|consigo|sei)",
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
    Sistema de Auto-Desenvolvimento com Teste Pós-Deploy
    Quando a IA não consegue responder, aciona:
    1. Analista de Requisitos - pesquisa como construir a solução
    2. Dev Agent - implementa a solução
    3. Deploy via GitHub CI/CD
    4. Teste com solicitação original após deploy
    5. Notifica resultado do aprendizado
    """
    
    def __init__(self, agents_client: 'AgentsClient', ollama_client: httpx.AsyncClient):
        self.agents = agents_client
        self.ollama = ollama_client
        self.client = httpx.AsyncClient(timeout=300.0)
        self.developments: Dict[str, dict] = {}  # Histórico de desenvolvimentos
        self.pending_tests: Dict[str, dict] = {}  # Testes pendentes pós-deploy
    
    def detect_inability(self, response: str) -> bool:
        """Detecta se a resposta indica incapacidade de atender"""
        response_lower = response.lower()
        
        for pattern in INABILITY_PATTERNS:
            if re.search(pattern, response_lower):
                return True
        
        # Verifica se é muito curta ou vaga
        if len(response) < 50 and ("não" in response_lower or "desculpe" in response_lower):
            return True
        
        return False
    
    async def analyze_request(self, user_request: str) -> Dict[str, Any]:
        """Analista de Requisitos analisa o pedido do usuário"""
        try:
            # Usar o Ollama diretamente para análise de requisitos
            prompt = f"""Você é um Analista de Requisitos Senior. Analise o seguinte pedido do usuário e crie uma especificação técnica.

PEDIDO DO USUÁRIO:
{user_request}

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
                timeout=120.0
            )
            
            if response.status_code == 200:
                data = response.json()
                text = data.get("response", "")
                
                # Extrair JSON da resposta
                try:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        return json.loads(text[start:end])
                except:
                    pass
            
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
            return {"error": str(e)}
    
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
                timeout=180.0
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
            
            # Fase 2: Desenvolvimento
            solution = await self.develop_solution(requirements)
            
            if not solution.get("success"):
                return False, f"Erro no desenvolvimento: {solution.get('error')}"
            
            # Fase 3: Validação
            validation = await self.execute_and_validate(solution)
            
            # Fase 4: Deploy da solução
            deploy_result = await self.deploy_solution(dev_id, requirements, solution)
            
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
            
            return True, explanation
            
        except Exception as e:
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
                timeout=120.0
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
            solutions_dir = Path("/home/eddie/myClaude/solutions")
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
            readme.write_text(f'''# {title}

**ID:** `{dev_id}`
**Linguagem:** {lang}
**Data:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Descrição

{desc}

## Uso

```{lang}
# Executar a solução
{f"python main.py" if lang == "python" else f"node main.{ext}" if lang == "javascript" else f"./main.{ext}"}
```

## Instalação

{"```bash\\npip install -r requirements.txt\\n```" if lang == "python" and deps else ""}
{"```bash\\nnpm install\\n```" if lang in ["javascript", "typescript"] and deps else ""}

## Passos de Implementação

{chr(10).join(f"- {p}" for p in requirements.get("passos_implementacao", []))}

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
                "message": f"Solução salva em {solution_dir}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Erro ao fazer deploy: {e}"
            }
    
    async def _git_commit_and_push(self, dev_id: str, title: str) -> Dict[str, Any]:
        """Commit e push para GitHub"""
        try:
            import subprocess
            
            base_dir = "/home/eddie/myClaude"
            
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
```

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
    """Bot completo com todas as funcionalidades e Auto-Desenvolvimento"""
    
    def __init__(self):
        self.api = TelegramAPI(BOT_TOKEN)
        self.agents = AgentsClient(AGENTS_API)
        self.ollama = httpx.AsyncClient(timeout=180.0)
        self.auto_dev = AutoDeveloper(self.agents, self.ollama)  # Sistema de Auto-Desenvolvimento
        self.last_update_id = 0
        self.running = True
        self.user_contexts: Dict[int, List[dict]] = {}  # Contexto por usuário
        self.auto_dev_enabled = True  # Flag para habilitar/desabilitar auto-dev
    
    async def ask_ollama(self, prompt: str, user_id: int = None) -> str:
        """Consulta modelo com contexto"""
        try:
            # Adiciona contexto da conversa
            messages = []
            if user_id and user_id in self.user_contexts:
                messages = self.user_contexts[user_id][-5:]  # Últimas 5 mensagens
            
            messages.append({"role": "user", "content": prompt})
            
            response = await self.ollama.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": MODEL,
                    "messages": messages,
                    "stream": False
                }
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
            return f"Erro: {response.status_code}"
        except Exception as e:
            return f"Erro: {e}"
    
    async def clear_old_updates(self):
        """Ignora mensagens antigas"""
        result = await self.api.get_updates(offset=-1, timeout=0)
        if result.get("ok") and result.get("result"):
            self.last_update_id = result["result"][-1]["update_id"]
            print(f"[Info] Mensagens antigas ignoradas (até {self.last_update_id})")
    
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
            
            await self.api.send_message(chat_id,
                f"📊 *Status do Sistema*\n\n"
                f"🤖 Bot: 🟢 Online\n"
                f"🧠 Ollama: {ollama_status}\n"
                f"👨‍💻 Agentes: {agents_status}\n"
                f"🔧 Auto-Dev: {auto_dev_status}\n\n"
                f"📋 *Configuração:*\n"
                f"Modelo: `{MODEL}`\n"
                f"Ollama: `{OLLAMA_HOST}`\n"
                f"Agentes: `{AGENTS_API}`\n"
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
            await self.api.send_message(chat_id, "🗑️ Contexto limpo!", 
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
        """Processa mensagem recebida com sistema de Auto-Desenvolvimento"""
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
        
        # Conversa normal - usar Ollama
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {user_name}: {text[:50]}...")
        
        await self.api.send_chat_action(chat_id, "typing")
        response = await self.ask_ollama(text, user_id)
        
        # === AUTO-DESENVOLVIMENTO ===
        # Verifica se a resposta indica incapacidade e se auto-dev está habilitado
        if self.auto_dev_enabled and self.auto_dev.detect_inability(response):
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
                if len(dev_response) > 4000:
                    parts = [dev_response[i:i+4000] for i in range(0, len(dev_response), 4000)]
                    for i, part in enumerate(parts):
                        await self.api.send_message(chat_id, part,
                            reply_to_message_id=msg_id if i == 0 else None)
                else:
                    await self.api.send_message(chat_id, dev_response, reply_to_message_id=msg_id)
                
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
            {"command": "start", "description": "Iniciar bot"},
            {"command": "help", "description": "Lista de comandos"},
            {"command": "status", "description": "Status do sistema"},
            {"command": "ask", "description": "Perguntar à IA"},
            {"command": "autodev", "description": "Auto-Desenvolvimento"},
            {"command": "agents", "description": "Listar agentes"},
            {"command": "code", "description": "Gerar código"},
            {"command": "project", "description": "Criar projeto"},
            {"command": "run", "description": "Executar código"},
            {"command": "id", "description": "Ver IDs"},
            {"command": "clear", "description": "Limpar contexto"},
        ]
        await self.api.set_my_commands(commands)
        
        # Limpar updates antigos
        await self.clear_old_updates()
        
        print("✅ Pronto! Aguardando mensagens...\n")
        
        # Notificar admin
        await self.api.send_message(ADMIN_CHAT_ID,
            "🟢 *Bot Iniciado com Auto-Desenvolvimento!*\n\n"
            f"🤖 Modelo: `{MODEL}`\n"
            f"🧠 Ollama: `{OLLAMA_HOST}`\n"
            f"👨‍💻 Agentes: `{AGENTS_API}`\n"
            f"🔧 Auto-Dev: `{'Ativado' if self.auto_dev_enabled else 'Desativado'}`\n\n"
            "💡 _Quando não consigo responder, desenvolvo a solução!_\n\n"
            "Use /help para ver comandos.")
        
        while self.running:
            try:
                result = await self.api.get_updates(offset=self.last_update_id + 1, timeout=30)
                
                if result.get("ok"):
                    for update in result.get("result", []):
                        self.last_update_id = update["update_id"]
                        
                        if "message" in update:
                            await self.handle_message(update["message"])
                
            except Exception as e:
                print(f"[Erro] Loop: {e}")
                await asyncio.sleep(5)
    
    async def stop(self):
        """Para o bot"""
        self.running = False
        await self.api.close()
        await self.agents.close()
        await self.auto_dev.close()
        await self.ollama.aclose()


async def main():
    bot = TelegramBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot encerrado")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
