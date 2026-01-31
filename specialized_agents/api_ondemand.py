"""
API FastAPI para os Agentes Especializados - Versão On-Demand
Componentes são iniciados apenas quando necessário e desligados após inatividade
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import asyncio
import io

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from specialized_agents.language_agents import AGENT_CLASSES
from specialized_agents.on_demand_manager import (
    get_on_demand_manager, 
    OnDemandManager,
    ComponentStatus
)

# ================== App Setup ==================
app = FastAPI(
    title="Specialized Agents API (On-Demand)",
    description="API para agentes programadores especializados - componentes sob demanda",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurações On-Demand
ON_DEMAND_CONFIG = {
    "agent_manager_timeout": 300,      # 5 min sem uso -> desliga
    "docker_timeout": 600,             # 10 min sem uso -> desliga
    "rag_timeout": 300,                # 5 min sem uso -> desliga
    "github_timeout": 180,             # 3 min sem uso -> desliga
    "cleanup_interval": 60,            # Verificar a cada 60s
}

# Gerenciador On-Demand
od_manager: Optional[OnDemandManager] = None

# Cache de componentes lazy
_agent_manager = None
_docker = None
_github_client = None


# ================== Funções Lazy Loading ==================

async def _start_agent_manager():
    """Inicia o AgentManager sob demanda"""
    global _agent_manager
    from specialized_agents import get_agent_manager
    
    _agent_manager = get_agent_manager()
    
    # Só inicializa se ainda não foi inicializado
    if not _agent_manager._initialized:
        await _agent_manager.initialize()
    
    return _agent_manager


async def _stop_agent_manager():
    """Para o AgentManager"""
    global _agent_manager
    
    if _agent_manager:
        try:
            # Marcar como não inicializado para poder reiniciar
            _agent_manager._initialized = False
            await _agent_manager.shutdown()
        except Exception as e:
            logger.warning(f"Erro ao fazer shutdown do AgentManager: {e}")
        _agent_manager = None


async def _start_docker():
    """Inicia Docker Orchestrator sob demanda"""
    global _docker
    from specialized_agents.docker_orchestrator import DockerOrchestrator
    _docker = DockerOrchestrator()
    return _docker


async def _stop_docker():
    """Para Docker Orchestrator e limpa containers"""
    global _docker
    if _docker:
        # Para containers gerenciados
        for container_id in list(_docker.containers.keys()):
            try:
                await _docker.stop_container(container_id)
            except:
                pass
        _docker = None


async def _start_github():
    """Inicia GitHub Client sob demanda"""
    global _github_client
    from specialized_agents.github_client import GitHubAgentClient
    _github_client = GitHubAgentClient()
    return _github_client


async def _stop_github():
    """Para GitHub Client"""
    global _github_client
    _github_client = None


async def get_manager():
    """Obtém AgentManager (inicia se necessário)"""
    return await od_manager.get("agent_manager")


async def get_docker():
    """Obtém Docker Orchestrator (inicia se necessário)"""
    return await od_manager.get("docker")


async def get_github():
    """Obtém GitHub Client (inicia se necessário)"""
    return await od_manager.get("github")


# ================== Startup/Shutdown ==================

@app.on_event("startup")
async def startup():
    """Startup leve - apenas registra componentes, não os inicia"""
    global od_manager
    od_manager = get_on_demand_manager()
    
    # Registrar componentes (NÃO inicia - lazy loading)
    od_manager.register(
        "agent_manager",
        start_func=_start_agent_manager,
        stop_func=_stop_agent_manager,
        idle_timeout_seconds=ON_DEMAND_CONFIG["agent_manager_timeout"]
    )
    
    od_manager.register(
        "docker",
        start_func=_start_docker,
        stop_func=_stop_docker,
        idle_timeout_seconds=ON_DEMAND_CONFIG["docker_timeout"]
    )
    
    od_manager.register(
        "github",
        start_func=_start_github,
        stop_func=_stop_github,
        idle_timeout_seconds=ON_DEMAND_CONFIG["github_timeout"]
    )
    
    # Iniciar loop de cleanup
    await od_manager.start_cleanup_loop()
    
    # Start lightweight agent_responder in this API process so coordinator broadcasts receive automated responses (useful for tests)
    try:
        from specialized_agents.agent_responder import start_responder
        start_responder()
        logger.info("agent_responder started in API process")
    except Exception as e:
        logger.warning(f"Não foi possível iniciar agent_responder: {e}")
    
    print("[API] Startup on-demand completo - componentes serão iniciados sob demanda")
    # Start lightweight responder for coordinator broadcasts so agents can auto-reply
    try:
        from specialized_agents.agent_responder import start_responder
        start_responder()
        logger.info("[API] Agent responder started for coordinator broadcasts")
    except Exception as e:
        logger.warning(f"[API] Could not start agent_responder: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown - para todos os componentes"""
    if od_manager:
        await od_manager.stop_cleanup_loop()
        await od_manager.stop_all()
    print("[API] Shutdown completo")


# ================== Models ==================

class CreateProjectRequest(BaseModel):
    language: str
    description: str
    project_name: Optional[str] = None


class ExecuteCodeRequest(BaseModel):
    language: str
    code: str
    run_tests: bool = True


class GenerateCodeRequest(BaseModel):
    language: str
    description: str
    context: Optional[str] = ""


class RAGSearchRequest(BaseModel):
    query: str
    language: Optional[str] = None
    n_results: int = 5


class RAGIndexRequest(BaseModel):
    content: str
    language: str
    content_type: str = "code"
    title: Optional[str] = ""
    description: Optional[str] = ""


class GitHubPushRequest(BaseModel):
    language: str
    project_name: str
    repo_name: Optional[str] = None
    description: str = ""


class DockerExecRequest(BaseModel):
    container_id: str
    command: str
    timeout: int = 60


class ConfigureGitHubRequest(BaseModel):
    token: str


class OnDemandConfigRequest(BaseModel):
    component: str
    timeout_seconds: int


# ================== Health & Status ==================

@app.get("/health")
async def health_check():
    """Health check leve - não inicia componentes"""
    return {
        "status": "healthy",
        "mode": "on-demand",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/status")
async def system_status():
    """Status do sistema incluindo componentes on-demand"""
    od_status = od_manager.get_status() if od_manager else {}
    
    # Verificar quais componentes estão rodando
    running = []
    stopped = []
    for name, comp in od_status.get("components", {}).items():
        if comp["status"] == "running":
            running.append(name)
        else:
            stopped.append(name)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "mode": "on-demand",
        "running_components": running,
        "stopped_components": stopped,
        "on_demand": od_status
    }


@app.get("/status/full")
async def full_system_status():
    """Status completo - INICIA o AgentManager se necessário"""
    manager = await get_manager()
    return await manager.get_system_status()


# ================== On-Demand Control ==================

@app.get("/ondemand/status")
async def ondemand_status():
    """Status detalhado dos componentes on-demand"""
    return od_manager.get_status()


@app.post("/ondemand/start/{component}")
async def ondemand_start(component: str):
    """Inicia um componente manualmente"""
    try:
        await od_manager.get(component)
        return {"success": True, "message": f"Componente {component} iniciado"}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao iniciar: {str(e)}")


@app.post("/ondemand/stop/{component}")
async def ondemand_stop(component: str):
    """Para um componente manualmente"""
    await od_manager.stop(component)
    return {"success": True, "message": f"Componente {component} parado"}


@app.post("/ondemand/stop-all")
async def ondemand_stop_all():
    """Para todos os componentes"""
    await od_manager.stop_all()
    return {"success": True, "message": "Todos os componentes parados"}


@app.post("/ondemand/configure")
async def ondemand_configure(request: OnDemandConfigRequest):
    """Configura timeout de um componente"""
    od_manager.set_idle_timeout(request.component, request.timeout_seconds)
    return {
        "success": True,
        "message": f"Timeout de {request.component} alterado para {request.timeout_seconds}s"
    }


# ================== Agents ==================

@app.get("/agents")
async def list_agents():
    """Lista agentes disponíveis (não inicia componentes)"""
    return {
        "available_languages": list(AGENT_CLASSES.keys()),
        "note": "Use /agents/{language} para ativar um agente sob demanda"
    }


@app.get("/agents/{language}")
async def get_agent_info(language: str):
    """Obtém info de um agente (INICIA se necessário)"""
    if language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {language}")
    
    manager = await get_manager()
    agent = manager.get_or_create_agent(language)
    return {
        "name": agent.name,
        "language": language,
        "capabilities": agent.capabilities,
        "status": agent.get_status()
    }


@app.get("/agents/active")
async def list_active_agents():
    """Lista apenas agentes já ativos (não inicia componentes)"""
    if not _agent_manager:
        return {"active_agents": [], "note": "AgentManager não iniciado"}
    
    return {"active_agents": _agent_manager.list_active_agents()}


# ================== Projects ==================

@app.post("/projects/create")
async def create_project(request: CreateProjectRequest):
    """Cria projeto (INICIA AgentManager se necessário)"""
    if request.language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {request.language}")
    
    manager = await get_manager()
    result = await manager.create_project(
        request.language,
        request.description,
        request.project_name
    )
    return result


@app.get("/projects/{language}")
async def list_projects(language: str):
    """Lista projetos (NÃO inicia componentes)"""
    from specialized_agents.config import PROJECTS_DIR
    
    projects = []
    lang_dir = PROJECTS_DIR / language
    
    if lang_dir.exists():
        for proj in lang_dir.iterdir():
            if proj.is_dir():
                projects.append({
                    "name": proj.name,
                    "path": str(proj),
                    "language": language
                })
    
    return {"projects": projects}


@app.get("/projects/{language}/{project_name}/download")
async def download_project(language: str, project_name: str):
    """Download projeto (INICIA AgentManager se necessário)"""
    manager = await get_manager()
    zip_data = await manager.download_project(language, project_name)
    
    if not zip_data:
        raise HTTPException(404, "Projeto não encontrado")
    
    return StreamingResponse(
        io.BytesIO(zip_data),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={project_name}.zip"}
    )


# ================== Code Execution ==================

@app.post("/code/generate")
async def generate_code(request: GenerateCodeRequest):
    """Gera código (INICIA AgentManager se necessário)"""
    if request.language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {request.language}")
    
    manager = await get_manager()
    agent = manager.get_or_create_agent(request.language)
    code = await agent.generate_code(request.description, request.context)
    tests = await agent.generate_tests(code, request.description)
    
    return {
        "language": request.language,
        "code": code,
        "tests": tests
    }


@app.post("/code/execute")
async def execute_code(request: ExecuteCodeRequest):
    """Executa código (INICIA AgentManager + Docker se necessário)"""
    if request.language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {request.language}")
    
    manager = await get_manager()
    result = await manager.execute_code(
        request.language,
        request.code,
        request.run_tests
    )
    return result


# ================== Docker ==================

@app.get("/docker/containers")
async def list_containers(language: Optional[str] = None):
    """Lista containers (INICIA Docker se necessário)"""
    docker = await get_docker()
    containers = docker.list_containers(language)
    return {"containers": containers}


@app.get("/docker/containers/{container_id}")
async def get_container(container_id: str):
    """Info de container (INICIA Docker se necessário)"""
    docker = await get_docker()
    info = docker.get_container_info(container_id)
    if not info:
        raise HTTPException(404, "Container não encontrado")
    return info


@app.post("/docker/containers/{container_id}/stop")
async def stop_container(container_id: str):
    """Para container"""
    docker = await get_docker()
    success = await docker.stop_container(container_id)
    return {"success": success}


@app.delete("/docker/containers/{container_id}")
async def remove_container(container_id: str, backup: bool = True):
    """Remove container"""
    docker = await get_docker()
    success = await docker.remove_container(container_id, backup=backup)
    return {"success": success}


@app.post("/docker/exec")
async def docker_exec(request: DockerExecRequest):
    """Executa comando em container"""
    docker = await get_docker()
    result = await docker.exec_command(
        request.container_id,
        request.command,
        request.timeout
    )
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


# ================== RAG ==================

@app.post("/rag/search")
async def rag_search(request: RAGSearchRequest):
    """Busca no RAG (carrega RAG sob demanda)"""
    from specialized_agents.rag_manager import RAGManagerFactory
    
    if request.language:
        rag = RAGManagerFactory.get_manager(request.language)
        results = await rag.search_with_metadata(request.query, request.n_results)
    else:
        results = await RAGManagerFactory.global_search(request.query, request.n_results)
    
    return {"results": results}


@app.post("/rag/index")
async def rag_index(request: RAGIndexRequest):
    """Indexa no RAG"""
    from specialized_agents.rag_manager import RAGManagerFactory
    
    rag = RAGManagerFactory.get_manager(request.language)
    
    if request.content_type == "code":
        success = await rag.index_code(request.content, request.language, request.description)
    elif request.content_type == "documentation":
        success = await rag.index_documentation(request.content, request.title)
    else:
        success = await rag.index_conversation(request.title, request.content)
    
    return {"success": success}


# ================== GitHub ==================

@app.get("/github/status")
async def github_status():
    """Status GitHub (NÃO inicia componentes)"""
    from specialized_agents.github_client import DirectGitHubClient
    
    direct_client = DirectGitHubClient()
    direct_connected = await direct_client.check_connection()
    
    user_info = None
    if direct_connected:
        user_result = await direct_client.get_user()
        if "error" not in user_result:
            user_info = {
                "login": user_result.get("login"),
                "name": user_result.get("name"),
                "html_url": user_result.get("html_url")
            }
    
    return {
        "direct_api_available": direct_connected,
        "has_token": bool(os.getenv("GITHUB_TOKEN")),
        "user": user_info
    }


@app.post("/github/push")
async def github_push(request: GitHubPushRequest):
    """Push para GitHub (INICIA componentes se necessário)"""
    manager = await get_manager()
    result = await manager.push_to_github(
        request.language,
        request.project_name,
        request.repo_name,
        request.description
    )
    return result


@app.get("/github/repos")
async def github_list_repos(owner: Optional[str] = None):
    """Lista repositórios"""
    github = await get_github()
    result = await github.list_repos(owner)
    return result.to_dict()


@app.post("/github/configure")
async def configure_github(request: ConfigureGitHubRequest):
    """Configura token GitHub"""
    os.environ["GITHUB_TOKEN"] = request.token
    
    # Salvar em .env
    env_path = Path(__file__).parent.parent / ".env"
    env_content = f'GITHUB_TOKEN={request.token}\n'
    
    if env_path.exists():
        with open(env_path) as f:
            lines = [l for l in f.readlines() if not l.startswith("GITHUB_TOKEN=")]
        env_content = "".join(lines) + env_content
    
    with open(env_path, "w") as f:
        f.write(env_content)
    
    # Verificar
    from specialized_agents.github_client import DirectGitHubClient
    direct = DirectGitHubClient()
    direct.token = request.token
    direct.headers["Authorization"] = f"token {request.token}"
    
    connected = await direct.check_connection()
    return {
        "success": connected,
        "message": "Token configurado!" if connected else "Token inválido"
    }


# ================== Cleanup ==================

@app.post("/cleanup/run")
async def run_cleanup():
    """Executa limpeza (INICIA AgentManager se necessário)"""
    manager = await get_manager()
    report = await manager.run_cleanup()
    return report


@app.get("/cleanup/storage")
async def storage_status():
    """Status de armazenamento"""
    manager = await get_manager()
    return await manager.cleanup_service.get_storage_status()


# ================== Run ==================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8503)
