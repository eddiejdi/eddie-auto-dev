"""
User Manager - Gerenciador de Usuários e Permissões SmartLife
"""

import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

logger = structlog.get_logger()


class UserRole(str, Enum):
    """Papéis de usuário."""

    ADMIN = "admin"  # Acesso total
    USER = "user"  # Controle de dispositivos permitidos
    GUEST = "guest"  # Apenas visualização e cenas
    BLOCKED = "blocked"  # Sem acesso


class PermissionLevel(str, Enum):
    """Níveis de permissão por dispositivo."""

    NONE = "none"  # Sem acesso
    VIEW = "view"  # Apenas visualizar
    CONTROL = "control"  # Visualizar e controlar
    FULL = "full"  # Visualizar, controlar e configurar


class UserManager:
    """
    Gerencia usuários e permissões do sistema SmartLife.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Cache de usuários
        self._users: Dict[str, Dict[str, Any]] = {}

        # Cache de permissões: {user_id: {device_id: permission}}
        self._permissions: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # IDs de admin configurados
        self._admin_telegram_ids = config.get("telegram", {}).get("admin_ids", [])
        self._admin_whatsapp_ids = config.get("whatsapp", {}).get("admin_numbers", [])

    async def start(self) -> None:
        """Inicializa o gerenciador de usuários."""
        logger.info("Iniciando User Manager...")

        # Carregar usuários do banco
        await self._load_users()

        # Criar admin padrão se não existir
        await self._ensure_admin_exists()

        logger.info(f"User Manager iniciado com {len(self._users)} usuários")

    async def _load_users(self) -> None:
        """Carrega usuários do banco de dados."""
        # TODO: Implementar carregamento do banco
        pass

    async def _ensure_admin_exists(self) -> None:
        """Garante que existe pelo menos um admin."""
        # Criar admins baseados na configuração
        for telegram_id in self._admin_telegram_ids:
            user_id = f"tg_{telegram_id}"
            if user_id not in self._users:
                self._users[user_id] = {
                    "id": user_id,
                    "telegram_id": telegram_id,
                    "whatsapp_id": None,
                    "name": "Admin",
                    "role": UserRole.ADMIN,
                    "is_active": True,
                    "created_at": datetime.now().isoformat(),
                }
                logger.info(f"Admin criado: {user_id}")

    # ========== CRUD de Usuários ==========

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Retorna todos os usuários."""
        return list(self._users.values())

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um usuário pelo ID."""
        return self._users.get(user_id)

    async def get_user_by_telegram(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Busca usuário por Telegram ID."""
        for user in self._users.values():
            if user.get("telegram_id") == telegram_id:
                return user
        return None

    async def get_user_by_whatsapp(self, whatsapp_id: str) -> Optional[Dict[str, Any]]:
        """Busca usuário por WhatsApp ID."""
        for user in self._users.values():
            if user.get("whatsapp_id") == whatsapp_id:
                return user
        return None

    async def create_user(
        self,
        telegram_id: Optional[int] = None,
        whatsapp_id: Optional[str] = None,
        name: str = "",
        role: str = "user",
    ) -> Dict[str, Any]:
        """
        Cria um novo usuário.

        Args:
            telegram_id: ID do Telegram
            whatsapp_id: Número do WhatsApp
            name: Nome do usuário
            role: Papel (admin, user, guest)
        """
        import uuid

        # Verificar se já existe
        if telegram_id:
            existing = await self.get_user_by_telegram(telegram_id)
            if existing:
                return {
                    "success": False,
                    "error": "Usuário já existe",
                    "user": existing,
                }

        if whatsapp_id:
            existing = await self.get_user_by_whatsapp(whatsapp_id)
            if existing:
                return {
                    "success": False,
                    "error": "Usuário já existe",
                    "user": existing,
                }

        user_id = f"user_{uuid.uuid4().hex[:8]}"
        user = {
            "id": user_id,
            "telegram_id": telegram_id,
            "whatsapp_id": whatsapp_id,
            "name": name,
            "role": (
                UserRole(role) if role in [r.value for r in UserRole] else UserRole.USER
            ),
            "is_active": True,
            "created_at": datetime.now().isoformat(),
        }

        self._users[user_id] = user
        self._permissions[user_id] = {}

        # TODO: Persistir no banco de dados

        logger.info(f"Usuário criado: {name} (ID: {user_id})")
        return {"success": True, "user_id": user_id, "user": user}

    async def update_user(
        self, user_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Atualiza dados de um usuário."""
        if user_id not in self._users:
            return {"success": False, "error": "Usuário não encontrado"}

        user = self._users[user_id]

        # Campos permitidos para atualização
        allowed_fields = ["name", "role", "is_active"]
        for field in allowed_fields:
            if field in updates:
                if field == "role":
                    user[field] = UserRole(updates[field])
                else:
                    user[field] = updates[field]

        user["updated_at"] = datetime.now().isoformat()

        return {"success": True, "user": user}

    async def delete_user(self, user_id: str) -> Dict[str, Any]:
        """Remove um usuário."""
        if user_id not in self._users:
            return {"success": False, "error": "Usuário não encontrado"}

        # Não permitir remover último admin
        user = self._users[user_id]
        if user.get("role") == UserRole.ADMIN:
            admin_count = sum(
                1 for u in self._users.values() if u.get("role") == UserRole.ADMIN
            )
            if admin_count <= 1:
                return {
                    "success": False,
                    "error": "Não é possível remover o último admin",
                }

        del self._users[user_id]
        if user_id in self._permissions:
            del self._permissions[user_id]

        # TODO: Remover do banco de dados

        return {"success": True}

    async def block_user(self, user_id: str) -> Dict[str, Any]:
        """Bloqueia um usuário."""
        return await self.update_user(user_id, {"role": UserRole.BLOCKED.value})

    async def unblock_user(self, user_id: str) -> Dict[str, Any]:
        """Desbloqueia um usuário (volta para role 'user')."""
        return await self.update_user(user_id, {"role": UserRole.USER.value})

    # ========== Permissões ==========

    async def set_permission(
        self,
        user_id: str,
        device_id: str,
        can_view: bool = True,
        can_control: bool = False,
        can_configure: bool = False,
    ) -> Dict[str, Any]:
        """
        Define permissões de um usuário para um dispositivo.

        Args:
            user_id: ID do usuário
            device_id: ID do dispositivo
            can_view: Pode visualizar
            can_control: Pode controlar
            can_configure: Pode configurar
        """
        if user_id not in self._users:
            return {"success": False, "error": "Usuário não encontrado"}

        if user_id not in self._permissions:
            self._permissions[user_id] = {}

        # Determinar nível de permissão
        if can_configure:
            level = PermissionLevel.FULL
        elif can_control:
            level = PermissionLevel.CONTROL
        elif can_view:
            level = PermissionLevel.VIEW
        else:
            level = PermissionLevel.NONE

        self._permissions[user_id][device_id] = {
            "level": level,
            "can_view": can_view,
            "can_control": can_control,
            "can_configure": can_configure,
            "updated_at": datetime.now().isoformat(),
        }

        # TODO: Persistir no banco de dados

        return {"success": True, "permission": self._permissions[user_id][device_id]}

    async def remove_permission(self, user_id: str, device_id: str) -> Dict[str, Any]:
        """Remove permissão de um usuário para um dispositivo."""
        if user_id in self._permissions and device_id in self._permissions[user_id]:
            del self._permissions[user_id][device_id]
            return {"success": True}
        return {"success": False, "error": "Permissão não encontrada"}

    async def get_user_permissions(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Retorna todas as permissões de um usuário."""
        return self._permissions.get(user_id, {})

    async def get_user_device_permissions(self, user_id: str) -> List[str]:
        """Retorna lista de device_ids que o usuário pode acessar."""
        user = self._users.get(user_id)
        if not user:
            return []

        # Admin tem acesso a tudo
        if user.get("role") == UserRole.ADMIN:
            return ["*"]  # Wildcard para todos

        # Outros usuários: verificar permissões específicas
        permissions = self._permissions.get(user_id, {})
        return [
            device_id
            for device_id, perm in permissions.items()
            if perm.get("can_view", False)
        ]

    async def check_permission(
        self, user_id: str, device_id: str, action: str = "view"
    ) -> bool:
        """
        Verifica se usuário tem permissão para ação em dispositivo.

        Args:
            user_id: ID do usuário
            device_id: ID do dispositivo
            action: Ação (view, control, configure)
        """
        user = self._users.get(user_id)
        if not user:
            return False

        # Usuário bloqueado não tem acesso
        if user.get("role") == UserRole.BLOCKED:
            return False

        # Admin tem acesso total
        if user.get("role") == UserRole.ADMIN:
            return True

        # Guest só pode visualizar
        if user.get("role") == UserRole.GUEST and action != "view":
            return False

        # Verificar permissões específicas
        user_perms = self._permissions.get(user_id, {})
        device_perm = user_perms.get(device_id, {})

        action_map = {
            "view": "can_view",
            "control": "can_control",
            "configure": "can_configure",
        }

        return device_perm.get(action_map.get(action, "can_view"), False)

    # ========== Autenticação ==========

    async def authenticate_telegram(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Autentica usuário por Telegram ID."""
        user = await self.get_user_by_telegram(telegram_id)

        if not user:
            # Auto-criar usuário se for admin configurado
            if telegram_id in self._admin_telegram_ids:
                result = await self.create_user(
                    telegram_id=telegram_id, name="Admin", role="admin"
                )
                return result.get("user")
            return None

        if not user.get("is_active") or user.get("role") == UserRole.BLOCKED:
            return None

        return user

    async def authenticate_whatsapp(self, whatsapp_id: str) -> Optional[Dict[str, Any]]:
        """Autentica usuário por WhatsApp ID."""
        user = await self.get_user_by_whatsapp(whatsapp_id)

        if not user:
            # Auto-criar usuário se for admin configurado
            if whatsapp_id in self._admin_whatsapp_ids:
                result = await self.create_user(
                    whatsapp_id=whatsapp_id, name="Admin", role="admin"
                )
                return result.get("user")
            return None

        if not user.get("is_active") or user.get("role") == UserRole.BLOCKED:
            return None

        return user

    def is_admin(self, user: Dict[str, Any]) -> bool:
        """Verifica se usuário é admin."""
        return user.get("role") == UserRole.ADMIN

    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de usuários."""
        total = len(self._users)
        by_role = {}

        for user in self._users.values():
            role = str(user.get("role", "unknown"))
            by_role[role] = by_role.get(role, 0) + 1

        active = sum(1 for u in self._users.values() if u.get("is_active"))

        return {"total": total, "active": active, "by_role": by_role}
