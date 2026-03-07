"""
User Management Endpoints - FastAPI Routes

Integração de endpoints REST para gerenciamento de usuários
Adicione ao specialized_agents/api.py
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import asyncio

from specialized_agents.user_management import (
    UserConfig,
    UserStatus,
    create_user,
    delete_user,
    get_user,
    list_users,
)

# Router
router = APIRouter(prefix="/api/users", tags=["User Management"])


# Modelos Pydantic
class CreateUserRequest(BaseModel):
    """Request para criar usuário"""

    username: str
    email: str
    full_name: str
    password: str
    groups: Optional[list[str]] = None
    quota_mb: int = 5000
    storage_quota_mb: int = 100000
    create_ssh_key: bool = True
    create_folders: bool = True
    send_welcome_email: bool = True


class UserResponse(BaseModel):
    """Response com dados do usuário"""

    username: str
    email: str
    full_name: str
    status: str
    created_at: str


class CreateUserResponse(BaseModel):
    """Response de criação bem-sucedida"""

    success: bool
    username: str
    email: str
    message: str
    steps: dict
    error: Optional[str] = None


# Endpoints
@router.post("/create", response_model=CreateUserResponse)
async def create_user_endpoint(
    request: CreateUserRequest,
    background_tasks: BackgroundTasks,
):
    """
    Criar novo usuário com pipeline completo

    **Pipeline:**
    1. Authentik - Criar conta central
    2. Email - Criar usuário de email
    3. Environment - Setup de home/SSH/folders
    4. Database - Registrar no banco

    **Exemplo:**
    ```json
    {
        "username": "edenilson",
        "email": "edenilson@rpa4all.com",
        "full_name": "Edenilson Silva",
        "password": "senhaSegura123!",
        "groups": ["users", "email_admins"],
        "quota_mb": 5000
    }
    ```
    """
    try:
        # Validações
        if not request.username or " " in request.username:
            raise HTTPException(400, "Nome de usuário inválido")

        if not request.email or "@" not in request.email:
            raise HTTPException(400, "Email inválido")

        if len(request.password) < 8:
            raise HTTPException(400, "Senha deve ter pelo menos 8 caracteres")

        # Criar config
        config = UserConfig(
            username=request.username,
            email=request.email,
            full_name=request.full_name,
            password=request.password,
            groups=request.groups or ["users"],
            quota_mb=request.quota_mb,
            storage_quota_mb=request.storage_quota_mb,
            create_ssh_key=request.create_ssh_key,
            create_folders=request.create_folders,
            send_welcome_email=request.send_welcome_email,
        )

        # Executar (assíncrono)
        result = await create_user(config)

        if result["success"]:
            return CreateUserResponse(
                success=True,
                username=request.username,
                email=request.email,
                message=f"Usuário {request.username} criado com sucesso!",
                steps=result["steps"],
            )
        else:
            return CreateUserResponse(
                success=False,
                username=request.username,
                email=request.email,
                message="Erro ao criar usuário",
                steps=result["steps"],
                error=result["error"],
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro interno: {str(e)}")


@router.delete("/delete/{username}")
async def delete_user_endpoint(username: str):
    """
    Deletar usuário de todos os sistemas

    Remove de:
    - Authentik
    - Email Server
    - Home directory
    - Database

    ⚠️ **Esta ação é irreversível!**
    """
    try:
        result = await delete_user(username)

        if result["success"]:
            return {
                "success": True,
                "message": f"Usuário {username} deletado com sucesso",
                "steps": result["steps"],
            }
        else:
            raise HTTPException(500, f"Erro deletando usuário: {result['error']}")

    except Exception as e:
        raise HTTPException(500, f"Erro: {str(e)}")


@router.get("/list")
async def list_users_endpoint():
    """
    Listar todos os usuários

    Retorna lista com:
    - username
    - email
    - full_name
    - status
    - created_at
    - updated_at
    """
    try:
        users = list_users()
        return {
            "total": len(users),
            "users": users,
        }
    except Exception as e:
        raise HTTPException(500, f"Erro listando usuários: {str(e)}")


@router.get("/get/{username}")
async def get_user_endpoint(username: str):
    """
    Obter dados de um usuário específico

    Retorna informações do usuário:
    ```json
    {
        "username": "edenilson",
        "email": "edenilson@rpa4all.com",
        "status": "complete",
        "created_at": "2026-03-07T10:00:00",
        ...
    }
    ```
    """
    try:
        user = get_user(username)

        if not user:
            raise HTTPException(404, f"Usuário não encontrado: {username}")

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro: {str(e)}")


@router.get("/status/{username}")
async def get_user_status(username: str):
    """
    Obter status de criação do usuário

    Retorna:
    ```json
    {
        "username": "edenilson",
        "status": "complete",
        "stages": {
            "authentik": true,
            "email": true,
            "environment": true
        }
    }
    ```
    """
    try:
        user = get_user(username)

        if not user:
            raise HTTPException(404, f"Usuário não encontrado: {username}")

        status = user.get("status")

        stages = {
            "authentik": status in [
                UserStatus.AUTHENTIK_CREATED.value,
                UserStatus.EMAIL_CREATED.value,
                UserStatus.ENV_SETUP.value,
                UserStatus.COMPLETE.value,
            ],
            "email": status in [
                UserStatus.EMAIL_CREATED.value,
                UserStatus.ENV_SETUP.value,
                UserStatus.COMPLETE.value,
            ],
            "environment": status in [
                UserStatus.ENV_SETUP.value,
                UserStatus.COMPLETE.value,
            ],
            "complete": status == UserStatus.COMPLETE.value,
        }

        return {
            "username": username,
            "status": status,
            "stages": stages,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check dos serviços"""
    import requests
    import os

    status = {
        "authentik": False,
        "email": False,
        "database": False,
    }

    # Check Authentik
    try:
        resp = requests.get(
            f"{os.getenv('AUTHENTIK_URL', 'https://auth.rpa4all.com')}/api/health/",
            timeout=2,
            verify=False,
        )
        status["authentik"] = resp.status_code == 200
    except:
        pass

    # Check Email
    try:
        import subprocess

        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "--quiet", "postfix"],
            capture_output=True,
            timeout=2,
        )
        status["email"] = result.returncode == 0
    except:
        pass

    # Check Database
    try:
        import psycopg2

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        conn.close()
        status["database"] = True
    except:
        pass

    all_ok = all(status.values())

    return {
        "healthy": all_ok,
        "services": status,
    }


# Para adicionar ao api.py:
# from specialized_agents.api_users import router as users_router
# app.include_router(users_router)
