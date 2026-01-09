"""
Cliente para envio de mensagens via Telegram
Suporta notificações, alertas e mensagens formatadas
"""
import os
import httpx
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class ParseMode(Enum):
    HTML = "HTML"
    MARKDOWN = "Markdown"
    MARKDOWN_V2 = "MarkdownV2"


@dataclass
class TelegramConfig:
    """Configuração do Telegram"""
    bot_token: str
    chat_id: str
    parse_mode: ParseMode = ParseMode.HTML
    disable_notification: bool = False
    
    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Carrega configuração das variáveis de ambiente"""
        return cls(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            parse_mode=ParseMode.HTML
        )


class TelegramClient:
    """
    Cliente para API do Telegram Bot
    
    Uso:
        client = TelegramClient.from_env()
        await client.send_message("Olá!")
    """
    
    BASE_URL = "https://api.telegram.org/bot{token}"
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.api_url = self.BASE_URL.format(token=config.bot_token)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @classmethod
    def from_env(cls) -> "TelegramClient":
        """Cria cliente a partir de variáveis de ambiente"""
        return cls(TelegramConfig.from_env())
    
    def is_configured(self) -> bool:
        """Verifica se o Telegram está configurado"""
        return bool(self.config.bot_token and self.config.chat_id)
    
    async def _request(self, method: str, data: Dict) -> Dict[str, Any]:
        """Faz requisição para API do Telegram"""
        try:
            response = await self.client.post(
                f"{self.api_url}/{method}",
                json=data
            )
            result = response.json()
            
            if not result.get("ok"):
                return {"success": False, "error": result.get("description", "Unknown error")}
            
            return {"success": True, "data": result.get("result")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def send_message(
        self,
        text: str,
        chat_id: str = None,
        parse_mode: ParseMode = None,
        disable_notification: bool = None,
        reply_markup: Dict = None
    ) -> Dict[str, Any]:
        """
        Envia mensagem de texto
        
        Args:
            text: Texto da mensagem
            chat_id: ID do chat (usa padrão se não informado)
            parse_mode: Modo de parse (HTML, Markdown, MarkdownV2)
            disable_notification: Silenciar notificação
            reply_markup: Teclado inline ou de resposta
        """
        data = {
            "chat_id": chat_id or self.config.chat_id,
            "text": text,
            "parse_mode": (parse_mode or self.config.parse_mode).value
        }
        
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        elif self.config.disable_notification:
            data["disable_notification"] = True
            
        if reply_markup:
            data["reply_markup"] = reply_markup
        
        return await self._request("sendMessage", data)
    
    async def send_document(
        self,
        document_path: str,
        caption: str = None,
        chat_id: str = None
    ) -> Dict[str, Any]:
        """Envia documento/arquivo"""
        try:
            with open(document_path, 'rb') as f:
                files = {"document": f}
                data = {"chat_id": chat_id or self.config.chat_id}
                if caption:
                    data["caption"] = caption
                
                response = await self.client.post(
                    f"{self.api_url}/sendDocument",
                    data=data,
                    files=files
                )
                result = response.json()
                
                if result.get("ok"):
                    return {"success": True, "data": result.get("result")}
                return {"success": False, "error": result.get("description")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def send_photo(
        self,
        photo_path: str,
        caption: str = None,
        chat_id: str = None
    ) -> Dict[str, Any]:
        """Envia foto"""
        try:
            with open(photo_path, 'rb') as f:
                files = {"photo": f}
                data = {"chat_id": chat_id or self.config.chat_id}
                if caption:
                    data["caption"] = caption
                
                response = await self.client.post(
                    f"{self.api_url}/sendPhoto",
                    data=data,
                    files=files
                )
                result = response.json()
                
                if result.get("ok"):
                    return {"success": True, "data": result.get("result")}
                return {"success": False, "error": result.get("description")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_me(self) -> Dict[str, Any]:
        """Obtém informações do bot"""
        return await self._request("getMe", {})
    
    async def get_updates(self, offset: int = None, limit: int = 100) -> Dict[str, Any]:
        """Obtém atualizações (mensagens recebidas)"""
        data = {"limit": limit}
        if offset:
            data["offset"] = offset
        return await self._request("getUpdates", data)


class TelegramNotifier:
    """
    Notificador de alto nível para enviar diferentes tipos de alertas
    """
    
    def __init__(self, client: TelegramClient = None):
        self.client = client or TelegramClient.from_env()
    
    async def notify_success(self, title: str, message: str) -> Dict:
        """Notificação de sucesso"""
        text = f"✅ <b>{title}</b>\n\n{message}"
        return await self.client.send_message(text)
    
    async def notify_error(self, title: str, message: str) -> Dict:
        """Notificação de erro"""
        text = f"❌ <b>{title}</b>\n\n{message}"
        return await self.client.send_message(text)
    
    async def notify_warning(self, title: str, message: str) -> Dict:
        """Notificação de aviso"""
        text = f"⚠️ <b>{title}</b>\n\n{message}"
        return await self.client.send_message(text)
    
    async def notify_info(self, title: str, message: str) -> Dict:
        """Notificação informativa"""
        text = f"ℹ️ <b>{title}</b>\n\n{message}"
        return await self.client.send_message(text)
    
    async def notify_deploy(
        self,
        project: str,
        status: str,
        url: str = None,
        details: str = None
    ) -> Dict:
        """Notificação de deploy"""
        emoji = "🚀" if status == "success" else "💥"
        status_text = "Sucesso" if status == "success" else "Falhou"
        
        text = f"{emoji} <b>Deploy {status_text}</b>\n\n"
        text += f"📦 Projeto: <code>{project}</code>\n"
        
        if url:
            text += f"🔗 URL: {url}\n"
        if details:
            text += f"\n📝 {details}"
        
        return await self.client.send_message(text)
    
    async def notify_github(
        self,
        action: str,
        repo: str,
        url: str,
        details: str = None
    ) -> Dict:
        """Notificação de ação no GitHub"""
        emojis = {
            "push": "📤",
            "pr": "🔀",
            "issue": "🐛",
            "release": "🎉",
            "star": "⭐"
        }
        emoji = emojis.get(action, "📌")
        
        text = f"{emoji} <b>GitHub: {action.upper()}</b>\n\n"
        text += f"📁 Repo: <code>{repo}</code>\n"
        text += f"🔗 {url}\n"
        
        if details:
            text += f"\n{details}"
        
        return await self.client.send_message(text)
    
    async def notify_training(
        self,
        model: str,
        status: str,
        conversations: int = 0,
        time_elapsed: float = 0
    ) -> Dict:
        """Notificação de treinamento de modelo"""
        emoji = "🎓" if status == "success" else "💔"
        
        text = f"{emoji} <b>Treinamento {status}</b>\n\n"
        text += f"🤖 Modelo: <code>{model}</code>\n"
        
        if conversations:
            text += f"💬 Conversas: {conversations}\n"
        if time_elapsed:
            text += f"⏱️ Tempo: {time_elapsed:.1f}s\n"
        
        return await self.client.send_message(text)
    
    async def notify_agent_task(
        self,
        agent: str,
        task: str,
        status: str,
        result_url: str = None
    ) -> Dict:
        """Notificação de tarefa de agente"""
        emoji = "✅" if status == "completed" else "🔄" if status == "running" else "❌"
        
        text = f"{emoji} <b>Agente: {agent}</b>\n\n"
        text += f"📋 Tarefa: {task}\n"
        text += f"📊 Status: {status}\n"
        
        if result_url:
            text += f"\n🔗 Resultado: {result_url}"
        
        return await self.client.send_message(text)


# ================== Funções de conveniência ==================

async def send_telegram(message: str) -> Dict:
    """Função simples para enviar mensagem"""
    client = TelegramClient.from_env()
    if not client.is_configured():
        return {"success": False, "error": "Telegram não configurado. Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID"}
    return await client.send_message(message)


async def notify(title: str, message: str, level: str = "info") -> Dict:
    """Função simples para notificar"""
    notifier = TelegramNotifier()
    
    if not notifier.client.is_configured():
        return {"success": False, "error": "Telegram não configurado"}
    
    methods = {
        "success": notifier.notify_success,
        "error": notifier.notify_error,
        "warning": notifier.notify_warning,
        "info": notifier.notify_info
    }
    
    method = methods.get(level, notifier.notify_info)
    return await method(title, message)


# ================== CLI para teste ==================

if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        client = TelegramClient.from_env()
        
        if not client.is_configured():
            print("❌ Telegram não configurado!")
            print("\nConfigure as variáveis de ambiente:")
            print("  TELEGRAM_BOT_TOKEN=seu_token")
            print("  TELEGRAM_CHAT_ID=seu_chat_id")
            print("\nPara obter o token, fale com @BotFather no Telegram")
            print("Para obter o chat_id, envie mensagem ao bot e acesse:")
            print("  https://api.telegram.org/bot<TOKEN>/getUpdates")
            return
        
        # Verificar bot
        print("🔍 Verificando bot...")
        me = await client.get_me()
        if me.get("success"):
            bot_info = me["data"]
            print(f"✅ Bot: @{bot_info.get('username')} ({bot_info.get('first_name')})")
        else:
            print(f"❌ Erro: {me.get('error')}")
            return
        
        # Enviar mensagem de teste
        if len(sys.argv) > 1:
            message = " ".join(sys.argv[1:])
        else:
            message = "🤖 Teste do bot Eddie Coder!\n\nIntegração funcionando corretamente."
        
        print(f"\n📤 Enviando mensagem...")
        result = await client.send_message(message)
        
        if result.get("success"):
            print("✅ Mensagem enviada com sucesso!")
        else:
            print(f"❌ Erro: {result.get('error')}")
    
    asyncio.run(main())
