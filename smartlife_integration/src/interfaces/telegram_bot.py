"""
SmartLife Telegram Bot Interface
Integra com o bot Telegram existente para controle de dispositivos
"""
import asyncio
import structlog
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

logger = structlog.get_logger()


class SmartLifeTelegramBot:
    """
    Interface Telegram para o SmartLife.
    Pode funcionar standalone ou integrado ao bot existente.
    """
    
    def __init__(
        self,
        token: str,
        smartlife_service,
        admin_ids: List[int] = None
    ):
        self.token = token
        self.smartlife = smartlife_service
        self.admin_ids = admin_ids or []
        
        self.app: Optional[Application] = None
    
    async def start(self) -> None:
        """Inicia o bot Telegram."""
        logger.info("Iniciando SmartLife Telegram Bot...")
        
        self.app = Application.builder().token(self.token).build()
        
        # Registrar handlers
        self._register_handlers()
        
        # Iniciar polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("SmartLife Telegram Bot iniciado")
    
    async def stop(self) -> None:
        """Para o bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
    
    def _register_handlers(self) -> None:
        """Registra handlers de comandos."""
        # Comandos básicos
        self.app.add_handler(CommandHandler("smartlife", self.cmd_menu))
        self.app.add_handler(CommandHandler("devices", self.cmd_devices))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        
        # Controle
        self.app.add_handler(CommandHandler("on", self.cmd_on))
        self.app.add_handler(CommandHandler("off", self.cmd_off))
        self.app.add_handler(CommandHandler("toggle", self.cmd_toggle))
        self.app.add_handler(CommandHandler("dim", self.cmd_dim))
        self.app.add_handler(CommandHandler("color", self.cmd_color))
        
        # Cenas
        self.app.add_handler(CommandHandler("scenes", self.cmd_scenes))
        self.app.add_handler(CommandHandler("scene", self.cmd_scene))
        
        # Automações
        self.app.add_handler(CommandHandler("automations", self.cmd_automations))
        
        # Admin
        self.app.add_handler(CommandHandler("users", self.cmd_users))
        self.app.add_handler(CommandHandler("adduser", self.cmd_adduser))
        self.app.add_handler(CommandHandler("deluser", self.cmd_deluser))
        self.app.add_handler(CommandHandler("refresh", self.cmd_refresh))
        
        # Callbacks de botões
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
    
    async def _get_user(self, update: Update) -> Optional[Dict[str, Any]]:
        """Autentica e retorna usuário."""
        telegram_id = update.effective_user.id
        return await self.smartlife.user_manager.authenticate_telegram(telegram_id)
    
    async def _check_admin(self, update: Update) -> bool:
        """Verifica se é admin."""
        user = await self._get_user(update)
        return user and self.smartlife.user_manager.is_admin(user)
    
    # ========== Comandos ==========
    
    async def cmd_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Menu principal do SmartLife."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text(
                "❌ Você não tem acesso ao SmartLife.\n"
                "Peça a um admin para adicionar você."
            )
            return
        
        keyboard = [
            [
                InlineKeyboardButton("🏠 Dispositivos", callback_data="sl_devices"),
                InlineKeyboardButton("📊 Status", callback_data="sl_status")
            ],
            [
                InlineKeyboardButton("🎬 Cenas", callback_data="sl_scenes"),
                InlineKeyboardButton("⚡ Automações", callback_data="sl_automations")
            ],
            [
                InlineKeyboardButton("🔄 Atualizar", callback_data="sl_refresh")
            ]
        ]
        
        if self.smartlife.user_manager.is_admin(user):
            keyboard.append([
                InlineKeyboardButton("👥 Usuários", callback_data="sl_users"),
                InlineKeyboardButton("⚙️ Config", callback_data="sl_config")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status = await self.smartlife.get_status()
        
        await update.message.reply_text(
            f"🏠 *SmartLife*\n\n"
            f"📱 Dispositivos: {status['devices']['online']}/{status['devices']['total']} online\n"
            f"⚡ Automações: {status['automations']['active']} ativas\n\n"
            f"Escolha uma opção:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def cmd_devices(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Lista dispositivos."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text("❌ Acesso negado.")
            return
        
        devices = await self.smartlife.get_devices(user_id=user["id"])
        
        if not devices:
            await update.message.reply_text("📭 Nenhum dispositivo encontrado.")
            return
        
        # Agrupar por room
        by_room: Dict[str, List] = {}
        for device in devices:
            room = device.get("room", "Outros") or "Outros"
            if room not in by_room:
                by_room[room] = []
            by_room[room].append(device)
        
        text = "🏠 *Dispositivos*\n\n"
        
        for room, room_devices in by_room.items():
            text += f"*{room}*\n"
            for device in room_devices:
                icon = device.get("type_info", {}).get("icon", "📱")
                status_icon = "🟢" if device.get("is_online") else "🔴"
                state = "ON" if device.get("state", {}).get("is_on") else "OFF"
                text += f"  {icon} {device['name']} {status_icon} ({state})\n"
            text += "\n"
        
        # Botões de controle rápido
        keyboard = []
        row = []
        for device in devices[:6]:  # Máximo 6 botões
            icon = "💡" if device.get("state", {}).get("is_on") else "⚫"
            row.append(InlineKeyboardButton(
                f"{icon} {device['name'][:10]}",
                callback_data=f"sl_toggle_{device['id']}"
            ))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔄 Atualizar", callback_data="sl_devices")])
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Status geral do sistema."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text("❌ Acesso negado.")
            return
        
        status = await self.smartlife.get_status()
        health = await self.smartlife.health_check()
        
        text = "📊 *Status do SmartLife*\n\n"
        text += f"*Sistema:* {'🟢 Online' if status['status'] == 'running' else '🔴 Offline'}\n\n"
        
        text += "*Dispositivos:*\n"
        text += f"  • Total: {status['devices']['total']}\n"
        text += f"  • Online: {status['devices']['online']} 🟢\n"
        text += f"  • Offline: {status['devices']['offline']} 🔴\n\n"
        
        text += "*Automações:*\n"
        text += f"  • Total: {status['automations']['total']}\n"
        text += f"  • Ativas: {status['automations']['active']}\n\n"
        
        text += "*Conexões:*\n"
        text += f"  • Local: {'🟢' if status['connections']['local'] else '🔴'}\n"
        text += f"  • Cloud: {'🟢' if status['connections']['cloud'] else '🔴'}\n"
        text += f"  • MQTT: {'🟢' if status['connections']['mqtt'] else '⚪'}\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Liga um dispositivo."""
        await self._control_device(update, context, "on")
    
    async def cmd_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Desliga um dispositivo."""
        await self._control_device(update, context, "off")
    
    async def cmd_toggle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Alterna estado de um dispositivo."""
        await self._control_device(update, context, "toggle")
    
    async def cmd_dim(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Ajusta brilho de uma lâmpada."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text("❌ Acesso negado.")
            return
        
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Uso: `/dim <dispositivo> <0-100>`\n"
                "Exemplo: `/dim sala 50`",
                parse_mode="Markdown"
            )
            return
        
        device_name = args[0]
        try:
            brightness = int(args[1])
        except ValueError:
            await update.message.reply_text("❌ Brilho deve ser um número de 0 a 100")
            return
        
        result = await self.smartlife.control_device(
            device_id=device_name,
            command="dim",
            value=brightness,
            user_id=user["id"]
        )
        
        if result.get("success"):
            await update.message.reply_text(f"🔆 Brilho de *{device_name}* ajustado para {brightness}%", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Erro: {result.get('error', 'Desconhecido')}")
    
    async def cmd_color(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Muda cor de uma lâmpada RGB."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text("❌ Acesso negado.")
            return
        
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Uso: `/color <dispositivo> <cor>`\n"
                "Cores: vermelho, verde, azul, amarelo, roxo, branco\n"
                "Exemplo: `/color quarto azul`",
                parse_mode="Markdown"
            )
            return
        
        device_name = args[0]
        color = args[1]
        
        result = await self.smartlife.control_device(
            device_id=device_name,
            command="color",
            value=color,
            user_id=user["id"]
        )
        
        if result.get("success"):
            await update.message.reply_text(f"🎨 Cor de *{device_name}* alterada para {color}", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Erro: {result.get('error', 'Desconhecido')}")
    
    async def _control_device(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        command: str
    ) -> None:
        """Controla um dispositivo."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text("❌ Acesso negado.")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                f"Uso: `/{command} <dispositivo>`\n"
                f"Exemplo: `/{command} sala`",
                parse_mode="Markdown"
            )
            return
        
        device_name = " ".join(args)
        
        result = await self.smartlife.control_device(
            device_id=device_name,
            command=command,
            user_id=user["id"]
        )
        
        if result.get("success"):
            icons = {"on": "💡", "off": "⚫", "toggle": "🔄"}
            await update.message.reply_text(
                f"{icons.get(command, '✅')} *{device_name}* - {command.upper()}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ Erro: {result.get('error', 'Desconhecido')}")
    
    async def cmd_scenes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Lista cenas disponíveis."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text("❌ Acesso negado.")
            return
        
        scenes = await self.smartlife.get_scenes(user_id=user["id"])
        
        if not scenes:
            await update.message.reply_text("📭 Nenhuma cena configurada.")
            return
        
        keyboard = []
        for scene in scenes:
            keyboard.append([InlineKeyboardButton(
                f"🎬 {scene['name']}",
                callback_data=f"sl_scene_{scene['id']}"
            )])
        
        await update.message.reply_text(
            "🎬 *Cenas Disponíveis*\n\nClique para executar:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    async def cmd_scene(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Executa uma cena."""
        user = await self._get_user(update)
        if not user:
            await update.message.reply_text("❌ Acesso negado.")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "Uso: `/scene <nome>`\n"
                "Exemplo: `/scene cinema`",
                parse_mode="Markdown"
            )
            return
        
        scene_name = " ".join(args)
        result = await self.smartlife.execute_scene(scene_name, user_id=user["id"])
        
        if result.get("success"):
            await update.message.reply_text(f"🎬 Cena *{scene_name}* executada!", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Erro: {result.get('error', 'Desconhecido')}")
    
    async def cmd_automations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Lista automações (admin only)."""
        if not await self._check_admin(update):
            await update.message.reply_text("❌ Apenas admins podem ver automações.")
            return
        
        automations = await self.smartlife.get_automations()
        
        if not automations:
            await update.message.reply_text("📭 Nenhuma automação configurada.")
            return
        
        text = "⚡ *Automações*\n\n"
        for auto in automations:
            status_icon = "🟢" if auto.get("is_active") else "🔴"
            text += f"{status_icon} *{auto['name']}*\n"
            text += f"   Trigger: {auto['trigger'].get('type', 'N/A')}\n"
            if auto.get("last_run"):
                text += f"   Último: {auto['last_run'][:16]}\n"
            text += "\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Lista usuários (admin only)."""
        if not await self._check_admin(update):
            await update.message.reply_text("❌ Apenas admins podem gerenciar usuários.")
            return
        
        users = await self.smartlife.get_users()
        
        text = "👥 *Usuários*\n\n"
        for user in users:
            role_icons = {"admin": "👑", "user": "👤", "guest": "👁", "blocked": "🚫"}
            icon = role_icons.get(str(user.get("role", "user")), "👤")
            status = "🟢" if user.get("is_active") else "🔴"
            text += f"{icon} {user.get('name', 'N/A')} {status}\n"
            if user.get("telegram_id"):
                text += f"   TG: `{user['telegram_id']}`\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Adiciona usuário (admin only)."""
        if not await self._check_admin(update):
            await update.message.reply_text("❌ Apenas admins podem adicionar usuários.")
            return
        
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Uso: `/adduser <telegram_id> <nome> [role]`\n"
                "Roles: admin, user, guest\n"
                "Exemplo: `/adduser 123456789 João user`",
                parse_mode="Markdown"
            )
            return
        
        try:
            telegram_id = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ Telegram ID deve ser um número")
            return
        
        name = args[1]
        role = args[2] if len(args) > 2 else "user"
        
        result = await self.smartlife.add_user(
            telegram_id=telegram_id,
            name=name,
            role=role
        )
        
        if result.get("success"):
            await update.message.reply_text(f"✅ Usuário *{name}* adicionado!", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Erro: {result.get('error', 'Desconhecido')}")
    
    async def cmd_deluser(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Remove usuário (admin only)."""
        if not await self._check_admin(update):
            await update.message.reply_text("❌ Apenas admins podem remover usuários.")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "Uso: `/deluser <telegram_id>`",
                parse_mode="Markdown"
            )
            return
        
        # TODO: Implementar remoção
        await update.message.reply_text("🚧 Funcionalidade em desenvolvimento")
    
    async def cmd_refresh(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Atualiza dispositivos (admin only)."""
        if not await self._check_admin(update):
            await update.message.reply_text("❌ Apenas admins podem atualizar dispositivos.")
            return
        
        msg = await update.message.reply_text("🔄 Atualizando dispositivos...")
        
        devices = await self.smartlife.device_manager.refresh_devices()
        
        await msg.edit_text(f"✅ {len(devices)} dispositivos atualizados!")
    
    # ========== Callbacks ==========
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Processa callbacks de botões inline."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = await self._get_user(update)
        
        if not user:
            await query.edit_message_text("❌ Acesso negado.")
            return
        
        if data == "sl_devices":
            await self._callback_devices(query, user)
        elif data == "sl_status":
            await self._callback_status(query)
        elif data == "sl_scenes":
            await self._callback_scenes(query, user)
        elif data.startswith("sl_toggle_"):
            device_id = data.replace("sl_toggle_", "")
            await self._callback_toggle(query, device_id, user)
        elif data.startswith("sl_scene_"):
            scene_id = data.replace("sl_scene_", "")
            await self._callback_scene(query, scene_id, user)
        elif data == "sl_refresh":
            await self._callback_refresh(query)
    
    async def _callback_devices(self, query, user) -> None:
        """Callback para listar dispositivos."""
        devices = await self.smartlife.get_devices(user_id=user["id"])
        
        text = "🏠 *Dispositivos*\n\n"
        for device in devices:
            icon = device.get("type_info", {}).get("icon", "📱")
            status = "🟢" if device.get("state", {}).get("is_on") else "⚫"
            text += f"{icon} {device['name']} {status}\n"
        
        keyboard = []
        row = []
        for device in devices[:6]:
            icon = "💡" if device.get("state", {}).get("is_on") else "⚫"
            row.append(InlineKeyboardButton(
                f"{icon} {device['name'][:8]}",
                callback_data=f"sl_toggle_{device['id']}"
            ))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔄 Atualizar", callback_data="sl_devices")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    async def _callback_status(self, query) -> None:
        """Callback para status."""
        status = await self.smartlife.get_status()
        
        text = f"📊 *Status*\n\n"
        text += f"Dispositivos: {status['devices']['online']}/{status['devices']['total']} online\n"
        text += f"Automações: {status['automations']['active']} ativas\n"
        text += f"Local: {'🟢' if status['connections']['local'] else '🔴'}\n"
        text += f"Cloud: {'🟢' if status['connections']['cloud'] else '🔴'}"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    async def _callback_scenes(self, query, user) -> None:
        """Callback para cenas."""
        scenes = await self.smartlife.get_scenes(user_id=user["id"])
        
        if not scenes:
            await query.edit_message_text("📭 Nenhuma cena configurada.")
            return
        
        keyboard = []
        for scene in scenes:
            keyboard.append([InlineKeyboardButton(
                f"🎬 {scene['name']}",
                callback_data=f"sl_scene_{scene['id']}"
            )])
        
        await query.edit_message_text(
            "🎬 *Cenas*\n\nClique para executar:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    async def _callback_toggle(self, query, device_id: str, user) -> None:
        """Callback para toggle de dispositivo."""
        result = await self.smartlife.toggle(device_id, user_id=user["id"])
        
        if result.get("success"):
            await query.answer("✅ Dispositivo alternado!")
            # Atualizar lista
            await self._callback_devices(query, user)
        else:
            await query.answer(f"❌ Erro: {result.get('error')}")
    
    async def _callback_scene(self, query, scene_id: str, user) -> None:
        """Callback para executar cena."""
        result = await self.smartlife.execute_scene(scene_id, user_id=user["id"])
        
        if result.get("success"):
            await query.answer("✅ Cena executada!")
        else:
            await query.answer(f"❌ Erro: {result.get('error')}")
    
    async def _callback_refresh(self, query) -> None:
        """Callback para refresh."""
        await query.answer("🔄 Atualizando...")
        await self.smartlife.device_manager.refresh_devices()
        await query.answer("✅ Atualizado!")


# ========== Funções para integração com bot existente ==========

def get_smartlife_handlers(smartlife_service) -> List:
    """
    Retorna handlers para integrar no bot Telegram existente.
    
    Uso no telegram_bot.py:
    ```
    from smartlife_integration.src.interfaces.telegram_bot import get_smartlife_handlers
    handlers = get_smartlife_handlers(smartlife_service)
    for handler in handlers:
        app.add_handler(handler)
    ```
    """
    bot = SmartLifeTelegramBot(
        token="",  # Não usado quando integrado
        smartlife_service=smartlife_service
    )
    
    return [
        CommandHandler("smartlife", bot.cmd_menu),
        CommandHandler("devices", bot.cmd_devices),
        CommandHandler("status", bot.cmd_status),
        CommandHandler("on", bot.cmd_on),
        CommandHandler("off", bot.cmd_off),
        CommandHandler("toggle", bot.cmd_toggle),
        CommandHandler("dim", bot.cmd_dim),
        CommandHandler("color", bot.cmd_color),
        CommandHandler("scenes", bot.cmd_scenes),
        CommandHandler("scene", bot.cmd_scene),
        CommandHandler("automations", bot.cmd_automations),
        CommandHandler("users", bot.cmd_users),
        CommandHandler("adduser", bot.cmd_adduser),
        CommandHandler("refresh", bot.cmd_refresh),
        CallbackQueryHandler(bot.handle_callback, pattern="^sl_"),
    ]
