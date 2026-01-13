"""
API FastAPI para os Agentes Especializados
Permite integração externa via REST API
"""
import os
import sys
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

# ================== App Setup ==================
app = FastAPI(
    title="Specialized Agents API",
    description="API para agentes programadores especializados por linguagem",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manager singleton
manager: Optional[AgentManager] = None


# ================== Startup/Shutdown ==================
@app.on_event("startup")
async def startup():
    global manager
    manager = get_agent_manager()
    await manager.initialize()


@app.on_event("shutdown")
async def shutdown():
    if manager:
        await manager.shutdown()


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
    return await manager.get_system_status()


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
