"""
Rotas FastAPI para o Homelab Agent.

Endpoints para execução remota de comandos no homelab com:
- Restrição de acesso por rede local (middleware)
- Validação de comandos (whitelist)
- Audit log
- Endpoints de conveniência (docker, systemd, health)
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from specialized_agents.homelab_agent import (
    get_homelab_agent,
    HomelabAgent,
    CommandCategory,
    is_local_ip,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/homelab", tags=["homelab"])


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    """Requisição para executar comando no homelab."""
    command: str = Field(..., description="Comando a executar", min_length=1, max_length=2000)
    timeout: Optional[int] = Field(30, description="Timeout em segundos", ge=1, le=300)

class ExecuteResponse(BaseModel):
    """Resposta de execução de comando."""
    success: bool
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    timestamp: str = ""
    error: Optional[str] = None
    category: Optional[str] = None

class DockerLogsRequest(BaseModel):
    """Requisição para logs de container."""
    container: str = Field(..., description="Nome ou ID do container")
    tail: int = Field(50, description="Número de linhas", ge=1, le=5000)

class ServiceRequest(BaseModel):
    """Requisição para operação em serviço systemd."""
    service: str = Field(..., description="Nome do serviço", min_length=1, max_length=200)

class JournalRequest(BaseModel):
    """Requisição para logs via journalctl."""
    service: str = Field(..., description="Nome do serviço")
    lines: int = Field(50, description="Número de linhas", ge=1, le=5000)

class AddPatternRequest(BaseModel):
    """Requisição para adicionar padrão permitido."""
    category: str = Field(..., description="Categoria do comando")
    pattern: str = Field(..., description="Regex do padrão permitido")

class ValidateCommandRequest(BaseModel):
    """Requisição para validar comando."""
    command: str = Field(..., description="Comando a validar")


# ---------------------------------------------------------------------------
# Dependência: verificação de rede local
# ---------------------------------------------------------------------------

def get_caller_ip(request: Request) -> str:
    """Extrai IP do chamador da requisição."""
    # Checar X-Forwarded-For (proxy reverso)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Checar X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # IP direto
    return request.client.host if request.client else "0.0.0.0"


async def require_local_network(request: Request) -> str:
    """Dependency que bloqueia acessos de fora da rede local."""
    caller_ip = get_caller_ip(request)
    if not is_local_ip(caller_ip):
        logger.warning(f"[Homelab API] Acesso negado de IP externo: {caller_ip}")
        raise HTTPException(
            status_code=403,
            detail=f"Acesso negado: IP {caller_ip} não está em rede local. "
                   f"Este endpoint aceita somente conexões de redes RFC 1918."
        )
    return caller_ip


def get_agent() -> HomelabAgent:
    """Retorna instância do HomelabAgent."""
    return get_homelab_agent()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def homelab_health(caller_ip: str = Depends(require_local_network)):
    """Health check do servidor homelab."""
    agent = get_agent()
    available = agent.is_available()
    return {
        "status": "online" if available else "offline",
        "host": agent.host,
        "user": agent.user,
        "caller_ip": caller_ip,
    }


@router.get("/server-health")
async def server_health(caller_ip: str = Depends(require_local_network)):
    """Status completo de saúde do servidor homelab."""
    agent = get_agent()
    try:
        health = await agent.server_health()
        return {"status": "success", "data": health, "caller_ip": caller_ip}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ExecuteResponse)
async def execute_command(
    req: ExecuteRequest,
    caller_ip: str = Depends(require_local_network),
):
    """
    Executa um comando no servidor homelab.
    
    O comando deve estar na whitelist de comandos permitidos.
    Somente acessível de redes locais (RFC 1918).
    """
    agent = get_agent()
    result = await agent.execute(req.command, timeout=req.timeout, caller_ip=caller_ip)
    return ExecuteResponse(**result.to_dict())


@router.post("/validate-command")
async def validate_command(
    req: ValidateCommandRequest,
    caller_ip: str = Depends(require_local_network),
):
    """Valida se um comando seria permitido sem executá-lo."""
    agent = get_agent()
    allowed, reason, category = agent.validate_command(req.command)
    return {
        "command": req.command,
        "allowed": allowed,
        "reason": reason,
        "category": category.value if category else None,
    }


# ---------------------------------------------------------------------------
# Docker endpoints
# ---------------------------------------------------------------------------

@router.get("/docker/ps")
async def docker_ps(
    all: bool = False,
    caller_ip: str = Depends(require_local_network),
):
    """Lista containers Docker no homelab."""
    agent = get_agent()
    result = await agent.docker_ps(all_containers=all)
    return ExecuteResponse(**result.to_dict())


@router.post("/docker/logs")
async def docker_logs(
    req: DockerLogsRequest,
    caller_ip: str = Depends(require_local_network),
):
    """Obtém logs de um container Docker."""
    agent = get_agent()
    result = await agent.docker_logs(req.container, req.tail)
    return ExecuteResponse(**result.to_dict())


@router.get("/docker/stats")
async def docker_stats(caller_ip: str = Depends(require_local_network)):
    """Uso de recursos dos containers Docker."""
    agent = get_agent()
    result = await agent.docker_stats()
    return ExecuteResponse(**result.to_dict())


@router.post("/docker/restart")
async def docker_restart(
    container: str,
    caller_ip: str = Depends(require_local_network),
):
    """Reinicia um container Docker."""
    agent = get_agent()
    result = await agent.docker_restart(container)
    return ExecuteResponse(**result.to_dict())


# ---------------------------------------------------------------------------
# Systemd endpoints
# ---------------------------------------------------------------------------

@router.post("/systemd/status")
async def systemd_status(
    req: ServiceRequest,
    caller_ip: str = Depends(require_local_network),
):
    """Status de um serviço systemd."""
    agent = get_agent()
    result = await agent.systemctl_status(req.service)
    return ExecuteResponse(**result.to_dict())


@router.post("/systemd/restart")
async def systemd_restart(
    req: ServiceRequest,
    caller_ip: str = Depends(require_local_network),
):
    """Reinicia um serviço systemd."""
    agent = get_agent()
    result = await agent.systemctl_restart(req.service)
    return ExecuteResponse(**result.to_dict())


@router.get("/systemd/list")
async def systemd_list(
    state: str = "running",
    caller_ip: str = Depends(require_local_network),
):
    """Lista serviços systemd por estado."""
    agent = get_agent()
    result = await agent.systemctl_list(state)
    return ExecuteResponse(**result.to_dict())


@router.post("/systemd/logs")
async def systemd_logs(
    req: JournalRequest,
    caller_ip: str = Depends(require_local_network),
):
    """Logs de um serviço via journalctl."""
    agent = get_agent()
    result = await agent.journalctl(req.service, req.lines)
    return ExecuteResponse(**result.to_dict())


# ---------------------------------------------------------------------------
# Sistema endpoints
# ---------------------------------------------------------------------------

@router.get("/system/disk")
async def system_disk(
    path: str = "/",
    caller_ip: str = Depends(require_local_network),
):
    """Uso de disco."""
    agent = get_agent()
    result = await agent.disk_usage(path)
    return ExecuteResponse(**result.to_dict())


@router.get("/system/memory")
async def system_memory(caller_ip: str = Depends(require_local_network)):
    """Uso de memória."""
    agent = get_agent()
    result = await agent.memory_usage()
    return ExecuteResponse(**result.to_dict())


@router.get("/system/cpu")
async def system_cpu(caller_ip: str = Depends(require_local_network)):
    """Info de CPU e carga."""
    agent = get_agent()
    result = await agent.cpu_info()
    return ExecuteResponse(**result.to_dict())


@router.get("/system/network")
async def system_network(caller_ip: str = Depends(require_local_network)):
    """Interfaces de rede."""
    agent = get_agent()
    result = await agent.network_info()
    return ExecuteResponse(**result.to_dict())


@router.get("/system/ports")
async def system_ports(caller_ip: str = Depends(require_local_network)):
    """Portas em escuta."""
    agent = get_agent()
    result = await agent.list_listening_ports()
    return ExecuteResponse(**result.to_dict())


# ---------------------------------------------------------------------------
# Audit & admin
# ---------------------------------------------------------------------------

@router.get("/audit")
async def get_audit_log(
    last_n: int = 50,
    caller_ip: str = Depends(require_local_network),
):
    """Retorna audit log das últimas operações."""
    agent = get_agent()
    return {
        "entries": agent.get_audit_log(last_n),
        "total": len(agent.audit_log),
    }


@router.get("/allowed-commands")
async def get_allowed_commands(caller_ip: str = Depends(require_local_network)):
    """Retorna categorias e padrões de comandos permitidos."""
    agent = get_agent()
    return agent.get_allowed_categories()


@router.post("/allowed-commands/add")
async def add_allowed_pattern(
    req: AddPatternRequest,
    caller_ip: str = Depends(require_local_network),
):
    """Adiciona um novo padrão de comando permitido em runtime."""
    try:
        category = CommandCategory(req.category)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Categoria inválida: {req.category}. "
                   f"Válidas: {', '.join(c.value for c in CommandCategory)}"
        )
    agent = get_agent()
    agent.add_allowed_pattern(category, req.pattern)
    return {"status": "success", "category": req.category, "pattern": req.pattern}
