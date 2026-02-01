"""
SmartLife API - User Routes
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..app import get_service

router = APIRouter()


# ================== Schemas ==================


class UserCreate(BaseModel):
    """Schema para criar usuário."""

    name: str = Field(..., description="Nome do usuário")
    role: str = Field("user", description="Role: admin, user, guest")
    telegram_id: Optional[int] = Field(None, description="ID do Telegram")
    whatsapp_id: Optional[str] = Field(None, description="Número WhatsApp")


class UserUpdate(BaseModel):
    """Schema para atualizar usuário."""

    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PermissionSet(BaseModel):
    """Schema para definir permissão."""

    device_id: str = Field(..., description="ID do dispositivo")
    can_view: bool = Field(True, description="Pode visualizar")
    can_control: bool = Field(False, description="Pode controlar")
    can_configure: bool = Field(False, description="Pode configurar")


# ================== Routes ==================


@router.get("/")
async def list_users():
    """Lista todos os usuários."""
    service = get_service()
    users = await service.get_users()
    return users


@router.get("/{user_id}")
async def get_user(user_id: str):
    """Obtém detalhes de um usuário."""
    service = get_service()
    user = await service.user_manager.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.post("/")
async def create_user(user: UserCreate):
    """
    Cria um novo usuário.

    Roles disponíveis:
    - admin: Acesso total ao sistema
    - user: Pode controlar dispositivos permitidos
    - guest: Apenas visualização
    """
    service = get_service()

    result = await service.add_user(
        name=user.name,
        role=user.role,
        telegram_id=user.telegram_id,
        whatsapp_id=user.whatsapp_id,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.put("/{user_id}")
async def update_user(user_id: str, user: UserUpdate):
    """Atualiza um usuário."""
    service = get_service()

    updates = {}
    if user.name is not None:
        updates["name"] = user.name
    if user.role is not None:
        updates["role"] = user.role
    if user.is_active is not None:
        updates["is_active"] = user.is_active

    result = await service.user_manager.update_user(user_id, updates)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.delete("/{user_id}")
async def deactivate_user(user_id: str):
    """
    Desativa um usuário.

    Não remove completamente, apenas marca como inativo.
    """
    service = get_service()
    result = await service.user_manager.deactivate_user(user_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/{user_id}/permissions")
async def get_user_permissions(user_id: str):
    """Lista permissões de um usuário."""
    service = get_service()
    permissions = await service.user_manager.get_user_permissions(user_id)
    return permissions


@router.post("/{user_id}/permissions")
async def set_user_permission(user_id: str, permission: PermissionSet):
    """
    Define permissão de um usuário para um dispositivo.

    Níveis de permissão:
    - can_view: Pode ver o estado do dispositivo
    - can_control: Pode controlar (ligar/desligar/etc.)
    - can_configure: Pode alterar configurações do dispositivo
    """
    service = get_service()

    result = await service.set_user_permission(
        user_id=user_id,
        device_id=permission.device_id,
        can_view=permission.can_view,
        can_control=permission.can_control,
        can_configure=permission.can_configure,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/{user_id}/permissions/bulk")
async def set_bulk_permissions(user_id: str, permissions: List[PermissionSet]):
    """Define múltiplas permissões de uma vez."""
    service = get_service()

    results = []
    for perm in permissions:
        result = await service.set_user_permission(
            user_id=user_id,
            device_id=perm.device_id,
            can_view=perm.can_view,
            can_control=perm.can_control,
            can_configure=perm.can_configure,
        )
        results.append(
            {"device_id": perm.device_id, "success": result.get("success", False)}
        )

    return {"user_id": user_id, "total": len(permissions), "results": results}


@router.delete("/{user_id}/permissions/{device_id}")
async def remove_user_permission(user_id: str, device_id: str):
    """Remove permissão de um usuário para um dispositivo."""
    service = get_service()

    result = await service.user_manager.remove_permission(user_id, device_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/telegram/{telegram_id}")
async def get_user_by_telegram(telegram_id: int):
    """Busca usuário por Telegram ID."""
    service = get_service()
    user = await service.user_manager.get_user_by_telegram(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/whatsapp/{whatsapp_id}")
async def get_user_by_whatsapp(whatsapp_id: str):
    """Busca usuário por WhatsApp ID."""
    service = get_service()
    user = await service.user_manager.get_user_by_whatsapp(whatsapp_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/admins/list")
async def list_admins():
    """Lista todos os administradores."""
    service = get_service()
    users = await service.get_users()
    admins = [u for u in users if u.get("role") == "admin"]
    return admins


@router.get("/roles/available")
async def list_available_roles():
    """Lista roles disponíveis."""
    return [
        {
            "role": "admin",
            "name": "Administrador",
            "description": "Acesso total ao sistema. Pode gerenciar dispositivos, usuários e automações.",
        },
        {
            "role": "user",
            "name": "Usuário",
            "description": "Pode controlar dispositivos conforme permissões. Não pode gerenciar outros usuários.",
        },
        {
            "role": "guest",
            "name": "Convidado",
            "description": "Acesso limitado. Pode apenas visualizar estados e executar cenas permitidas.",
        },
    ]
