"""
SmartLife Database Repository Classes
"""
import asyncio
import structlog
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update, delete, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Device, User, Permission, Automation, Scene, Event, DeviceState,
    DeviceType, UserRole, AutomationTriggerType
)

logger = structlog.get_logger()


class DeviceRepository:
    """Repository para operações com dispositivos."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all(self) -> List[Device]:
        """Lista todos os dispositivos."""
        result = await self.session.execute(select(Device))
        return list(result.scalars().all())
    
    async def get_by_id(self, device_id: str) -> Optional[Device]:
        """Busca dispositivo por ID."""
        result = await self.session.execute(
            select(Device).where(Device.id == device_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_room(self, room: str) -> List[Device]:
        """Lista dispositivos de um cômodo."""
        result = await self.session.execute(
            select(Device).where(Device.room == room)
        )
        return list(result.scalars().all())
    
    async def get_by_type(self, device_type: DeviceType) -> List[Device]:
        """Lista dispositivos de um tipo."""
        result = await self.session.execute(
            select(Device).where(Device.type == device_type)
        )
        return list(result.scalars().all())
    
    async def get_online(self) -> List[Device]:
        """Lista dispositivos online."""
        result = await self.session.execute(
            select(Device).where(Device.is_online == True)
        )
        return list(result.scalars().all())
    
    async def create(self, device_data: Dict[str, Any]) -> Device:
        """Cria um novo dispositivo."""
        device = Device(**device_data)
        self.session.add(device)
        await self.session.commit()
        await self.session.refresh(device)
        return device
    
    async def update(self, device_id: str, data: Dict[str, Any]) -> Optional[Device]:
        """Atualiza um dispositivo."""
        device = await self.get_by_id(device_id)
        if not device:
            return None
        
        for key, value in data.items():
            if hasattr(device, key):
                setattr(device, key, value)
        
        device.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(device)
        return device
    
    async def update_state(self, device_id: str, state: Dict[str, Any]) -> bool:
        """Atualiza estado de um dispositivo."""
        result = await self.session.execute(
            update(Device)
            .where(Device.id == device_id)
            .values(
                current_state=state,
                is_online=True,
                last_online=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def set_offline(self, device_id: str) -> bool:
        """Marca dispositivo como offline."""
        result = await self.session.execute(
            update(Device)
            .where(Device.id == device_id)
            .values(is_online=False, updated_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def delete(self, device_id: str) -> bool:
        """Remove um dispositivo."""
        result = await self.session.execute(
            delete(Device).where(Device.id == device_id)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def save_state_history(
        self, 
        device_id: str, 
        state: Dict[str, Any],
        metrics: Optional[Dict[str, float]] = None
    ) -> DeviceState:
        """Salva histórico de estado do dispositivo."""
        state_record = DeviceState(
            device_id=device_id,
            state=state,
            is_online=True,
            power=metrics.get("power") if metrics else None,
            current=metrics.get("current") if metrics else None,
            voltage=metrics.get("voltage") if metrics else None,
            energy=metrics.get("energy") if metrics else None,
            temperature=metrics.get("temperature") if metrics else None,
            humidity=metrics.get("humidity") if metrics else None,
        )
        self.session.add(state_record)
        await self.session.commit()
        return state_record


class UserRepository:
    """Repository para operações com usuários."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all(self) -> List[User]:
        """Lista todos os usuários."""
        result = await self.session.execute(select(User).where(User.is_active == True))
        return list(result.scalars().all())
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Busca usuário por ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Busca usuário por Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_whatsapp_id(self, whatsapp_id: str) -> Optional[User]:
        """Busca usuário por WhatsApp ID."""
        result = await self.session.execute(
            select(User).where(User.whatsapp_id == whatsapp_id)
        )
        return result.scalar_one_or_none()
    
    async def get_admins(self) -> List[User]:
        """Lista administradores."""
        result = await self.session.execute(
            select(User).where(
                and_(User.role == UserRole.ADMIN, User.is_active == True)
            )
        )
        return list(result.scalars().all())
    
    async def create(
        self,
        name: str,
        role: UserRole = UserRole.USER,
        telegram_id: Optional[int] = None,
        whatsapp_id: Optional[str] = None,
        email: Optional[str] = None
    ) -> User:
        """Cria um novo usuário."""
        user = User(
            name=name,
            role=role,
            telegram_id=telegram_id,
            whatsapp_id=whatsapp_id,
            email=email
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def update(self, user_id: int, data: Dict[str, Any]) -> Optional[User]:
        """Atualiza um usuário."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        for key, value in data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        user.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def update_activity(self, user_id: int) -> bool:
        """Atualiza última atividade do usuário."""
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_activity=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def deactivate(self, user_id: int) -> bool:
        """Desativa um usuário."""
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_user_permissions(self, user_id: int) -> List[Permission]:
        """Lista permissões de um usuário."""
        result = await self.session.execute(
            select(Permission).where(Permission.user_id == user_id)
        )
        return list(result.scalars().all())
    
    async def set_permission(
        self,
        user_id: int,
        device_id: str,
        can_view: bool = True,
        can_control: bool = False,
        can_configure: bool = False
    ) -> Permission:
        """Define permissão de usuário para dispositivo."""
        # Verificar se já existe
        result = await self.session.execute(
            select(Permission).where(
                and_(
                    Permission.user_id == user_id,
                    Permission.device_id == device_id
                )
            )
        )
        permission = result.scalar_one_or_none()
        
        if permission:
            permission.can_view = can_view
            permission.can_control = can_control
            permission.can_configure = can_configure
        else:
            permission = Permission(
                user_id=user_id,
                device_id=device_id,
                can_view=can_view,
                can_control=can_control,
                can_configure=can_configure
            )
            self.session.add(permission)
        
        await self.session.commit()
        await self.session.refresh(permission)
        return permission
    
    async def check_permission(
        self,
        user_id: int,
        device_id: str,
        action: str = "view"
    ) -> bool:
        """Verifica se usuário tem permissão para ação no dispositivo."""
        # Admin tem todas permissões
        user = await self.get_by_id(user_id)
        if user and user.role == UserRole.ADMIN:
            return True
        
        result = await self.session.execute(
            select(Permission).where(
                and_(
                    Permission.user_id == user_id,
                    Permission.device_id == device_id
                )
            )
        )
        permission = result.scalar_one_or_none()
        
        if not permission:
            return False
        
        if action == "view":
            return permission.can_view
        elif action == "control":
            return permission.can_control
        elif action == "configure":
            return permission.can_configure
        
        return False


class AutomationRepository:
    """Repository para operações com automações."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all(self) -> List[Automation]:
        """Lista todas as automações."""
        result = await self.session.execute(select(Automation))
        return list(result.scalars().all())
    
    async def get_enabled(self) -> List[Automation]:
        """Lista automações ativas."""
        result = await self.session.execute(
            select(Automation).where(Automation.is_enabled == True)
        )
        return list(result.scalars().all())
    
    async def get_by_id(self, automation_id: int) -> Optional[Automation]:
        """Busca automação por ID."""
        result = await self.session.execute(
            select(Automation).where(Automation.id == automation_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_trigger_type(self, trigger_type: AutomationTriggerType) -> List[Automation]:
        """Lista automações por tipo de trigger."""
        result = await self.session.execute(
            select(Automation).where(
                and_(
                    Automation.trigger_type == trigger_type,
                    Automation.is_enabled == True
                )
            )
        )
        return list(result.scalars().all())
    
    async def create(
        self,
        name: str,
        trigger_type: AutomationTriggerType,
        trigger_config: Dict[str, Any],
        actions: List[Dict[str, Any]],
        conditions: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Automation:
        """Cria uma nova automação."""
        automation = Automation(
            name=name,
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            actions=actions,
            conditions=conditions or [],
            description=description,
            created_by=created_by
        )
        self.session.add(automation)
        await self.session.commit()
        await self.session.refresh(automation)
        return automation
    
    async def update(self, automation_id: int, data: Dict[str, Any]) -> Optional[Automation]:
        """Atualiza uma automação."""
        automation = await self.get_by_id(automation_id)
        if not automation:
            return None
        
        for key, value in data.items():
            if hasattr(automation, key):
                setattr(automation, key, value)
        
        automation.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(automation)
        return automation
    
    async def toggle(self, automation_id: int, enabled: bool) -> bool:
        """Ativa ou desativa uma automação."""
        result = await self.session.execute(
            update(Automation)
            .where(Automation.id == automation_id)
            .values(is_enabled=enabled, updated_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def record_execution(self, automation_id: int, error: Optional[str] = None) -> bool:
        """Registra execução de automação."""
        result = await self.session.execute(
            update(Automation)
            .where(Automation.id == automation_id)
            .values(
                last_executed=datetime.utcnow(),
                execution_count=Automation.execution_count + 1,
                last_error=error
            )
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def delete(self, automation_id: int) -> bool:
        """Remove uma automação."""
        result = await self.session.execute(
            delete(Automation).where(Automation.id == automation_id)
        )
        await self.session.commit()
        return result.rowcount > 0


class SceneRepository:
    """Repository para operações com cenas."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all(self) -> List[Scene]:
        """Lista todas as cenas."""
        result = await self.session.execute(select(Scene))
        return list(result.scalars().all())
    
    async def get_by_id(self, scene_id: int) -> Optional[Scene]:
        """Busca cena por ID."""
        result = await self.session.execute(
            select(Scene).where(Scene.id == scene_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[Scene]:
        """Busca cena por nome."""
        result = await self.session.execute(
            select(Scene).where(Scene.name.ilike(f"%{name}%"))
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        name: str,
        actions: List[Dict[str, Any]],
        description: Optional[str] = None,
        icon: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Scene:
        """Cria uma nova cena."""
        scene = Scene(
            name=name,
            actions=actions,
            description=description,
            icon=icon,
            created_by=created_by
        )
        self.session.add(scene)
        await self.session.commit()
        await self.session.refresh(scene)
        return scene
    
    async def update(self, scene_id: int, data: Dict[str, Any]) -> Optional[Scene]:
        """Atualiza uma cena."""
        scene = await self.get_by_id(scene_id)
        if not scene:
            return None
        
        for key, value in data.items():
            if hasattr(scene, key):
                setattr(scene, key, value)
        
        await self.session.commit()
        await self.session.refresh(scene)
        return scene
    
    async def record_execution(self, scene_id: int) -> bool:
        """Registra execução de cena."""
        result = await self.session.execute(
            update(Scene)
            .where(Scene.id == scene_id)
            .values(
                last_executed=datetime.utcnow(),
                execution_count=Scene.execution_count + 1
            )
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def delete(self, scene_id: int) -> bool:
        """Remove uma cena."""
        result = await self.session.execute(
            delete(Scene).where(Scene.id == scene_id)
        )
        await self.session.commit()
        return result.rowcount > 0


class EventRepository:
    """Repository para operações com eventos."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def log_event(
        self,
        event_type: str,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        device_id: Optional[str] = None,
        user_id: Optional[int] = None,
        automation_id: Optional[int] = None,
        severity: str = "info"
    ) -> Event:
        """Registra um evento."""
        event = Event(
            event_type=event_type,
            message=message,
            data=data,
            device_id=device_id,
            user_id=user_id,
            automation_id=automation_id,
            severity=severity
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
    
    async def get_recent(self, limit: int = 100) -> List[Event]:
        """Lista eventos recentes."""
        result = await self.session.execute(
            select(Event).order_by(desc(Event.created_at)).limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_by_device(self, device_id: str, limit: int = 50) -> List[Event]:
        """Lista eventos de um dispositivo."""
        result = await self.session.execute(
            select(Event)
            .where(Event.device_id == device_id)
            .order_by(desc(Event.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_by_type(self, event_type: str, limit: int = 50) -> List[Event]:
        """Lista eventos por tipo."""
        result = await self.session.execute(
            select(Event)
            .where(Event.event_type == event_type)
            .order_by(desc(Event.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_errors(self, hours: int = 24) -> List[Event]:
        """Lista erros das últimas X horas."""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(Event)
            .where(
                and_(
                    Event.severity == "error",
                    Event.created_at >= since
                )
            )
            .order_by(desc(Event.created_at))
        )
        return list(result.scalars().all())
    
    async def cleanup_old(self, days: int = 30) -> int:
        """Remove eventos antigos."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            delete(Event).where(Event.created_at < cutoff)
        )
        await self.session.commit()
        return result.rowcount
