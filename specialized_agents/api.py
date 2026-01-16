"""
API FastAPI para os Agentes Especializados
Permite integração externa via REST API
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

# Adicionar ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from specialized_agents import get_agent_manager, AgentManager
from specialized_agents.language_agents import AGENT_CLASSES
from specialized_agents.interceptor_routes import router as interceptor_router
from specialized_agents.agent_interceptor import get_agent_interceptor
from specialized_agents.distributed_routes import router as distributed_router

# Logger
logger = logging.getLogger(__name__)

# ================== App Setup ==================
app = FastAPI(
    title="Specialized Agents API",
    description="API para agentes programadores especializados por linguagem",
    version="1.0.0"
)

# Incluir rotas do coordenador distribuído
app.include_router(distributed_router)

# Incluir rotas do interceptador
app.include_router(interceptor_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manager singleton
manager: Optional[AgentManager] = None
autoscaler = None
instructor = None
interceptor = None


# ================== Startup/Shutdown ==================
@app.on_event("startup")
async def startup():
    global manager, autoscaler, instructor, interceptor
    manager = get_agent_manager()
    await manager.initialize()
    
    # Iniciar auto-scaler
    from specialized_agents.autoscaler import get_autoscaler
    autoscaler = get_autoscaler()
    await autoscaler.start()
    
    # Iniciar instructor agent
    from specialized_agents.instructor_agent import get_instructor
    instructor = get_instructor()
    await instructor.start()
    
    # Iniciar interceptador de conversas
    interceptor = get_agent_interceptor()
    logger.info("🎯 Agent Conversation Interceptor iniciado")


@app.on_event("shutdown")
async def shutdown():
    global autoscaler, instructor
    if manager:
        await manager.shutdown()
    if autoscaler:
        await autoscaler.stop()
    if instructor:
        await instructor.stop()


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
    content_type: str = "code"  # code, documentation, conversation
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


# ================== Health & Status ==================
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/status")
async def system_status():
    if not manager:
        raise HTTPException(500, "Manager not initialized")
    status = await manager.get_system_status()
    
    # Adicionar status do auto-scaler
    if autoscaler:
        status["autoscaler"] = autoscaler.get_status()
    
    return status


# ================== Auto-Scaling ==================
@app.get("/autoscaler/status")
async def autoscaler_status():
    """Status do auto-scaler"""
    if not autoscaler:
        raise HTTPException(500, "Auto-scaler not initialized")
    return autoscaler.get_status()


@app.get("/autoscaler/metrics")
async def autoscaler_metrics():
    """Métricas de recursos do sistema"""
    import psutil
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(),
        "memory": {
            "total_gb": psutil.virtual_memory().total / (1024**3),
            "used_gb": psutil.virtual_memory().used / (1024**3),
            "percent": psutil.virtual_memory().percent
        },
        "disk": {
            "total_gb": psutil.disk_usage('/').total / (1024**3),
            "used_gb": psutil.disk_usage('/').used / (1024**3),
            "percent": psutil.disk_usage('/').percent
        },
        "recommended_parallelism": autoscaler.get_recommended_parallelism() if autoscaler else 4
    }


@app.post("/autoscaler/scale")
async def manual_scale(target_agents: int):
    """Escala manualmente o número de agents"""
    if not autoscaler:
        raise HTTPException(500, "Auto-scaler not initialized")
    
    from specialized_agents.config import AUTOSCALING_CONFIG
    min_a = AUTOSCALING_CONFIG["min_agents"]
    max_a = AUTOSCALING_CONFIG["max_agents"]
    
    if target_agents < min_a or target_agents > max_a:
        raise HTTPException(400, f"Target deve estar entre {min_a} e {max_a}")
    
    old = autoscaler.current_agents
    autoscaler.current_agents = target_agents
    
    return {
        "success": True,
        "old_agents": old,
        "new_agents": target_agents,
        "message": f"Escalado de {old} para {target_agents} agents"
    }


# ================== Instructor Agent ==================
@app.get("/instructor/status")
async def get_instructor_status():
    """Obtém status do Instructor Agent"""
    global instructor
    if not instructor:
        raise HTTPException(503, "Instructor não inicializado")
    
    return instructor.get_status()


@app.post("/instructor/train/{language}")
async def train_language(language: str, query: Optional[str] = None):
    """Força treinamento para uma linguagem específica"""
    global instructor
    if not instructor:
        raise HTTPException(503, "Instructor não inicializado")
    
    result = await instructor.train_specific_language(language, query)
    return result


@app.post("/instructor/train-all")
async def train_all():
    """Força treinamento completo de todas linguagens"""
    global instructor
    if not instructor:
        raise HTTPException(503, "Instructor não inicializado")
    
    result = await instructor.train_all_agents()
    return result


@app.get("/instructor/history")
async def get_training_history(limit: int = 10):
    """Obtém histórico de treinamentos"""
    global instructor
    if not instructor:
        raise HTTPException(503, "Instructor não inicializado")
    
    return {
        "history": instructor.training_history[-limit:],
        "total_sessions": len(instructor.training_history)
    }


@app.get("/instructor/sources")
async def get_knowledge_sources():
    """Lista todas as fontes de conhecimento configuradas"""
    from specialized_agents.instructor_agent import KNOWLEDGE_SOURCES
    return {
        "sources": KNOWLEDGE_SOURCES,
        "total_languages": len(KNOWLEDGE_SOURCES)
    }


# ================== Agents ==================
@app.get("/agents")
async def list_agents():
    """Lista todos os agentes disponíveis"""
    return {
        "available_languages": list(AGENT_CLASSES.keys()),
        "active_agents": manager.list_active_agents() if manager else []
    }


@app.get("/agents/{language}")
async def get_agent_info(language: str):
    """Obtém informações de um agente específico"""
    if language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {language}")
    
    agent = manager.get_or_create_agent(language)
    return {
        "name": agent.name,
        "language": language,
        "capabilities": agent.capabilities,
        "status": agent.get_status()
    }


@app.post("/agents/{language}/activate")
async def activate_agent(language: str):
    """Ativa um agente"""
    if language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {language}")
    
    agent = manager.get_or_create_agent(language)
    return {"message": f"Agente {agent.name} ativado", "agent": agent.get_status()}


# ================== BPM Agent (Diagramas) ==================
@app.get("/bpm/templates")
async def list_bpm_templates():
    """Lista templates de diagramas disponíveis"""
    from specialized_agents.bpm_agent import get_bpm_agent
    agent = get_bpm_agent()
    return {
        "templates": agent.list_templates(),
        "capabilities": agent.get_capabilities()
    }


class BPMDiagramRequest(BaseModel):
    template: str
    name: Optional[str] = None


@app.post("/bpm/diagram")
async def create_bpm_diagram(request: BPMDiagramRequest):
    """Cria diagrama a partir de template"""
    from specialized_agents.bpm_agent import get_bpm_agent
    agent = get_bpm_agent()
    
    try:
        output_path = agent.create_from_template(request.template, request.name)
        return {
            "success": True,
            "path": output_path,
            "template": request.template,
            "message": f"Diagrama criado: {output_path}"
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


class BPMCustomDiagramRequest(BaseModel):
    name: str
    elements: List[Dict[str, Any]]
    flows: List[Dict[str, Any]]


@app.post("/bpm/diagram/custom")
async def create_custom_bpm_diagram(request: BPMCustomDiagramRequest):
    """Cria diagrama customizado"""
    from specialized_agents.bpm_agent import get_bpm_agent
    agent = get_bpm_agent()
    
    try:
        output_path = agent.create_custom_diagram(
            request.elements,
            request.flows,
            request.name
        )
        return {
            "success": True,
            "path": output_path,
            "name": request.name,
            "elements_count": len(request.elements),
            "flows_count": len(request.flows)
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/bpm/diagram/{filename}")
async def download_diagram(filename: str):
    """Download de diagrama .drawio"""
    from specialized_agents.bpm_agent import DIAGRAMS_DIR
    
    filepath = DIAGRAMS_DIR / filename
    if not filepath.exists():
        # Tentar com extensão
        filepath = DIAGRAMS_DIR / f"{filename}.drawio"
    
    if not filepath.exists():
        raise HTTPException(404, f"Diagrama não encontrado: {filename}")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={filepath.name}"}
    )


# ================== Projects ==================
@app.post("/projects/create")
async def create_project(request: CreateProjectRequest):
    """Cria novo projeto com agente especializado"""
    if request.language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {request.language}")
    
    result = await manager.create_project(
        request.language,
        request.description,
        request.project_name
    )
    
    return result


@app.get("/projects/{language}")
async def list_projects(language: str):
    """Lista projetos de uma linguagem"""
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
    """Download projeto como ZIP"""
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
    """Gera código usando agente especializado"""
    if request.language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {request.language}")
    
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
    """Executa código em container"""
    if request.language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {request.language}")
    
    result = await manager.execute_code(
        request.language,
        request.code,
        request.run_tests
    )
    
    return result


@app.post("/code/analyze-error")
async def analyze_error(language: str, code: str, error: str):
    """Analisa erro e sugere correção"""
    agent = manager.get_or_create_agent(language)
    analysis = await agent.analyze_error(code, error)
    return analysis


# ================== File Upload/Download ==================
@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    project_name: Optional[str] = Form(None),
    auto_run: bool = Form(False)
):
    """Upload de arquivo"""
    content = await file.read()
    
    result = await manager.upload_and_process(
        content,
        file.filename,
        language,
        auto_run
    )
    
    return result


@app.post("/files/upload-zip")
async def upload_zip(
    file: UploadFile = File(...),
    project_name: Optional[str] = Form(None),
    auto_build: bool = Form(False)
):
    """Upload de projeto ZIP"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(400, "Arquivo deve ser .zip")
    
    content = await file.read()
    result = await manager.upload_zip_project(content, project_name, auto_build)
    
    return result


@app.get("/files/list")
async def list_files(
    directory: Optional[str] = None,
    language: Optional[str] = None
):
    """Lista arquivos"""
    files = await manager.file_manager.list_files(directory, language)
    return {"files": files}


# ================== Docker ==================
@app.get("/docker/containers")
async def list_containers(language: Optional[str] = None):
    """Lista containers"""
    containers = manager.docker.list_containers(language)
    return {"containers": containers}


@app.get("/docker/containers/{container_id}")
async def get_container(container_id: str):
    """Obtém info de container"""
    info = manager.docker.get_container_info(container_id)
    if not info:
        raise HTTPException(404, "Container não encontrado")
    return info


@app.post("/docker/containers/{container_id}/start")
async def start_container(container_id: str):
    """Inicia container"""
    success = await manager.docker.start_container(container_id)
    return {"success": success}


@app.post("/docker/containers/{container_id}/stop")
async def stop_container(container_id: str):
    """Para container"""
    success = await manager.docker.stop_container(container_id)
    return {"success": success}


@app.delete("/docker/containers/{container_id}")
async def remove_container(container_id: str, backup: bool = True):
    """Remove container"""
    success = await manager.docker.remove_container(container_id, backup=backup)
    return {"success": success}


@app.post("/docker/exec")
async def docker_exec(request: DockerExecRequest):
    """Executa comando em container"""
    result = await manager.docker.exec_command(
        request.container_id,
        request.command,
        request.timeout
    )
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


@app.get("/docker/containers/{container_id}/logs")
async def get_container_logs(container_id: str, lines: int = 100):
    """Obtém logs de container"""
    logs = await manager.docker.get_logs(container_id, lines)
    return {"logs": logs}


# ================== RAG ==================
@app.post("/rag/search")
async def rag_search(request: RAGSearchRequest):
    """Busca no RAG"""
    if request.language:
        from specialized_agents.rag_manager import RAGManagerFactory
        rag = RAGManagerFactory.get_manager(request.language)
        results = await rag.search_with_metadata(request.query, request.n_results)
    else:
        results = await manager.search_rag_all_languages(request.query, request.n_results)
    
    return {"results": results}


@app.post("/rag/index")
async def rag_index(request: RAGIndexRequest):
    """Indexa conteúdo no RAG"""
    from specialized_agents.rag_manager import RAGManagerFactory
    
    rag = RAGManagerFactory.get_manager(request.language)
    
    if request.content_type == "code":
        success = await rag.index_code(
            request.content,
            request.language,
            request.description
        )
    elif request.content_type == "documentation":
        success = await rag.index_documentation(
            request.content,
            request.title
        )
    else:
        success = await rag.index_conversation(
            request.title,
            request.content
        )
    
    return {"success": success}


@app.get("/rag/stats/{language}")
async def rag_stats(language: str):
    """Estatísticas do RAG"""
    from specialized_agents.rag_manager import RAGManagerFactory
    rag = RAGManagerFactory.get_manager(language)
    return await rag.get_stats()


# ================== GitHub ==================
@app.post("/github/push")
async def github_push(request: GitHubPushRequest):
    """Push projeto para GitHub"""
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
    result = await manager.github_client.list_repos(owner)
    return result.to_dict()


@app.get("/github/repos/{owner}/{repo}/issues")
async def github_list_issues(owner: str, repo: str, state: str = "open"):
    """Lista issues"""
    result = await manager.github_client.list_issues(owner, repo, state)
    return result.to_dict()


# ================== Cleanup ==================
@app.post("/cleanup/run")
async def run_cleanup(background_tasks: BackgroundTasks):
    """Executa limpeza"""
    report = await manager.run_cleanup()
    return report


@app.get("/cleanup/storage")
async def storage_status():
    """Status de armazenamento"""
    return await manager.cleanup_service.get_storage_status()


@app.get("/cleanup/backups")
async def list_backups(backup_type: Optional[str] = None):
    """Lista backups"""
    backups = manager.cleanup_service.list_backups(backup_type)
    return {"backups": backups}


@app.post("/cleanup/restore/{backup_path:path}")
async def restore_backup(backup_path: str, destination: Optional[str] = None):
    """Restaura backup"""
    success = await manager.cleanup_service.restore_backup(backup_path, destination)
    return {"success": success}


# ================== Agent Communication Bus ==================
from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
    log_coordinator
)


@app.get("/communication/messages")
async def get_communication_messages(
    limit: int = 100,
    source: Optional[str] = None,
    target: Optional[str] = None,
    message_type: Optional[str] = None
):
    """Obtém mensagens de comunicação entre agentes"""
    bus = get_communication_bus()
    
    # Filtrar por tipo se especificado
    msg_types = None
    if message_type:
        try:
            msg_types = [MessageType(message_type)]
        except ValueError:
            pass
    
    messages = bus.get_messages(
        limit=limit,
        message_types=msg_types,
        source=source,
        target=target
    )
    
    return {
        "messages": [m.to_dict() for m in messages],
        "total": len(messages),
        "stats": bus.get_stats()
    }


@app.get("/communication/stats")
async def get_communication_stats():
    """Obtém estatísticas de comunicação"""
    bus = get_communication_bus()
    return bus.get_stats()


@app.post("/communication/clear")
async def clear_communication_log():
    """Limpa o log de comunicação"""
    bus = get_communication_bus()
    bus.clear()
    return {"success": True, "message": "Log de comunicação limpo"}


@app.post("/communication/pause")
async def pause_communication_recording():
    """Pausa a gravação de comunicação"""
    bus = get_communication_bus()
    bus.pause_recording()
    return {"success": True, "recording": False}


@app.post("/communication/resume")
async def resume_communication_recording():
    """Retoma a gravação de comunicação"""
    bus = get_communication_bus()
    bus.resume_recording()
    return {"success": True, "recording": True}


@app.post("/communication/test")
async def send_test_message(message: str = "Mensagem de teste via API"):
    """Envia mensagem de teste"""
    log_coordinator(message)
    return {"success": True, "message": "Mensagem de teste enviada"}


@app.get("/communication/export")
async def export_communication_log(format: str = "json"):
    """Exporta log de comunicação"""
    bus = get_communication_bus()
    export_data = bus.export_messages(format=format.lower())
    
    if format.lower() == "json":
        return JSONResponse(content={"data": export_data})
    else:
        return StreamingResponse(
            io.BytesIO(export_data.encode()),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=communication_log.md"}
        )


class FilterRequest(BaseModel):
    message_type: str
    enabled: bool


@app.post("/communication/filter")
async def set_communication_filter(request: FilterRequest):
    """Define filtro de tipo de mensagem"""
    bus = get_communication_bus()
    bus.set_filter(request.message_type, request.enabled)
    return {"success": True, "filter": request.message_type, "enabled": request.enabled}


# ================== Run ==================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8503)
