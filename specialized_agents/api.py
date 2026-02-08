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

# Jira routes (board, sync, distribute)
try:
    from specialized_agents.jira.routes import router as jira_router
    from specialized_agents.jira.cloud_routes import router as jira_cloud_router
    JIRA_ROUTES_OK = True
except Exception:
    JIRA_ROUTES_OK = False

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

# Incluir rotas Jira
if JIRA_ROUTES_OK:
    app.include_router(jira_router)
    app.include_router(jira_cloud_router)
    logger.info("📋 Jira routes registered (/jira/*)")
else:
    logger.warning("⚠️  Jira routes not loaded (missing dependencies)")

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
    # Start a lightweight Telegram poller early so inbound updates
    # are captured even while the API finishes other startup tasks.
    try:
        from specialized_agents.telegram_poller import start_poller
        start_poller()
        logger.info("🔎 Telegram poller started early (captures inbound updates)")
    except Exception:
        logger.exception("Failed to start Telegram poller")

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
    # Start Telegram bridge inside this process so it can subscribe to the central bus
    try:
        from specialized_agents.telegram_bridge import start_bridge
        start_bridge()
        logger.info("🔌 Telegram bridge started and subscribed to bus")
    except Exception:
        logger.exception("Failed to start Telegram bridge")
    # Start automatic telegram responder for simple director confirmations
    try:
        from specialized_agents.telegram_auto_responder import start_auto_responder
        start_auto_responder()
        logger.info("🤖 Telegram auto-responder started")
    except Exception:
        logger.exception("Failed to start telegram auto-responder")
    # (poller already started early)

    # Start lightweight agent_responder so coordinator broadcasts receive automated responses
    # This ensures the responder runs in the main API process (useful for tests and CI)
    try:
        from specialized_agents.agent_responder import start_responder
        start_responder()
        logger.info("agent_responder started in API process")
    except Exception as e:
        logger.exception(f"Could not start agent_responder: {e}")

    # Install a lightweight in-process coordinator responder used for tests:
    try:
        from specialized_agents.agent_communication_bus import get_communication_bus, MessageType, log_response, log_error

        def _coordinator_test_handler(message):
            try:
                if message.message_type != MessageType.COORDINATOR:
                    return
                # look for the please_respond op in JSON or plain text
                op = None
                try:
                    payload = json.loads(message.content)
                    op = payload.get("op")
                except Exception:
                    if "please_respond" in message.content or "por favor respondam" in message.content:
                        op = "please_respond"

                if op != "please_respond":
                    return

                def _respond():
                    try:
                        # small delay to allow agents to initialize
                        time.sleep(0.2)
                        active = manager.list_active_agents() if manager else []
                        if not active:
                            log_response("assistant", "coordinator", "Nenhum agente ativo disponível para responder ao broadcast")
                            return
                        for a in active:
                            agent_name = a.get("name") or a.get("language")
                            content = f"{agent_name} resposta automática ao broadcast: {message.content[:200]}"
                            log_response(agent_name, "coordinator", content)
                    except Exception as e:
                        try:
                            log_error("api_responder", f"Erro ao responder broadcast: {e}")
                        except Exception:
                            pass

                threading.Thread(target=_respond, daemon=True).start()
            except Exception as e:
                try:
                    log_error("api_responder", f"_coordinator_test_handler exception: {e}")
                except Exception:
                    pass

        bus = get_communication_bus()
        bus.subscribe(_coordinator_test_handler)
        # announce subscription for observability
        try:
            log_response("api_responder", "coordinator", "api_responder subscribed to coordinator broadcasts")
        except Exception:
            pass
    except Exception:
        logger.exception("Failed to install in-process coordinator responder (test helper)")


@app.get("/debug/communication/subscribers")
async def debug_comm_subscribers():
    """Returns number of subscribers on the communication bus (debug helper)"""
    try:
        bus = get_communication_bus()
        return {"count": len(bus.subscribers)}
    except Exception as e:
        logger.exception("Failed to get subscribers")
        raise HTTPException(status_code=500, detail=str(e))



@app.on_event("shutdown")
async def shutdown():
    global autoscaler, instructor
    if manager:
        await manager.shutdown()
    if autoscaler:
        await autoscaler.stop()
    if instructor:
        await instructor.stop()


# -------------------- Debug endpoints --------------------
@app.post("/debug/responder/start")
async def debug_start_responder():
    """Debug endpoint to start the lightweight agent_responder inside the running process.
    Useful for tests and manual debugging when the responder wasn't started at startup.
    """
    try:
        from specialized_agents.agent_responder import start_responder
        start_responder()
        return {"status": "ok", "message": "agent_responder started"}
    except Exception as e:
        logger.exception("Failed to start agent_responder via debug endpoint")
        raise HTTPException(status_code=500, detail=str(e))


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


class BPMGenerateRequest(BaseModel):
    description: str
    name: Optional[str] = None


@app.post("/bpm/generate")
async def generate_bpm_from_description(request: BPMGenerateRequest):
    """
    Gera diagrama a partir de descrição em linguagem natural.
    Usa Ollama LOCAL para economizar tokens do Copilot.
    """
    from specialized_agents.bpm_agent import get_bpm_agent
    agent = get_bpm_agent()
    
    try:
        output_path = await agent.generate_from_description(
            request.description,
            request.name
        )
        return {
            "success": True,
            "path": output_path,
            "description": request.description,
            "message": "Diagrama gerado via Ollama LOCAL (economia de tokens)",
            "provider": "ollama_local"
        }
    except Exception as e:
        raise HTTPException(500, f"Erro ao gerar diagrama: {str(e)}")


@app.get("/bpm/diagrams")
async def list_diagrams():
    """Lista todos os diagramas gerados"""
    from specialized_agents.bpm_agent import DIAGRAMS_DIR
    
    diagrams = []
    if DIAGRAMS_DIR.exists():
        for f in DIAGRAMS_DIR.glob("*.drawio"):
            diagrams.append({
                "name": f.stem,
                "filename": f.name,
                "size_kb": f.stat().st_size / 1024,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
    
    return {"diagrams": diagrams, "count": len(diagrams)}


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


@app.post("/code/generate-stream")
async def generate_code_stream(request: GenerateCodeRequest):
    """Gera código com streaming em tempo real via Ollama + debug do bus"""
    if request.language not in AGENT_CLASSES:
        raise HTTPException(404, f"Linguagem não suportada: {request.language}")

    from openwebui_integration import OLLAMA_HOST, MODEL_PROFILES
    from specialized_agents.agent_communication_bus import (
        get_communication_bus, MessageType,
        log_task_start, log_task_end, log_llm_call,
        log_llm_response, log_code_generation, log_error,
    )
    import json as _json
    import httpx
    import uuid

    model_name = MODEL_PROFILES.get("coder", {}).get("model", "qwen2.5-coder:7b")
    system_prompt = MODEL_PROFILES.get("coder", {}).get("system_prompt", "")
    task_id = f"gen_{uuid.uuid4().hex[:8]}"

    prompt = (
        f"Gere código {request.language} para: {request.description}\n\n"
        "Requisitos:\n- Retorne APENAS o código, sem explicações."
    )

    def _bus_event(msg_type: str, source: str, target: str, content: str) -> str:
        """Formata mensagem do bus como SSE inline"""
        ts = datetime.now().strftime("%H:%M:%S")
        payload = _json.dumps(
            {"type": msg_type, "source": source, "target": target,
             "content": content, "ts": ts, "task_id": task_id},
            ensure_ascii=False,
        )
        return f"data: [BUS] {payload}\n\n"

    async def event_stream():
        total_chars = 0
        try:
            # ── Bus: task start ──
            log_task_start("api", task_id, f"Geração {request.language}: {request.description[:120]}")
            yield _bus_event("task_start", "api", "system",
                             f"Iniciando geração de código {request.language}")

            # ── Bus: LLM call ──
            log_llm_call("api", prompt[:200], model=model_name, task_id=task_id)
            yield _bus_event("llm_call", "api", "ollama",
                             f"Chamando {model_name} (prompt: {len(prompt)} chars)")

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_HOST}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": True,
                        "options": {"temperature": 0.1}
                    },
                ) as resp:
                    first_chunk = True
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = _json.loads(line)
                        except Exception:
                            continue

                        chunk = data.get("response", "")
                        if chunk:
                            total_chars += len(chunk)
                            if first_chunk:
                                yield _bus_event("llm_response", "ollama", "api",
                                                 "Primeiro token recebido — streaming iniciado")
                                first_chunk = False
                            yield f"data: {chunk}\n\n"

                        if data.get("done"):
                            # ── Bus: LLM response complete ──
                            log_llm_response("api", f"({total_chars} chars gerados)",
                                             model=model_name, task_id=task_id)
                            yield _bus_event("llm_response", "ollama", "api",
                                             f"Streaming concluído — {total_chars} caracteres gerados")

                            # ── Bus: code generation ──
                            log_code_generation("api", request.description[:200],
                                                code_snippet="", task_id=task_id)
                            yield _bus_event("code_gen", "api", "user",
                                             f"Código {request.language} gerado ({total_chars} chars)")

                            # ── Bus: task end ──
                            log_task_end("api", task_id, "success")
                            yield _bus_event("task_end", "api", "system",
                                             f"Task {task_id} concluída com sucesso")

                            yield "data: [DONE]\n\n"
                            break
        except Exception as e:
            log_error("api", f"Erro na geração: {e}", task_id=task_id)
            yield _bus_event("error", "api", "system", f"Erro: {str(e)}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/bus/stream")
async def bus_message_stream(limit: int = 50):
    """SSE endpoint para streaming de mensagens do bus em tempo real"""
    from specialized_agents.agent_communication_bus import get_communication_bus
    import json as _json

    bus = get_communication_bus()
    queue: asyncio.Queue = asyncio.Queue()

    def _on_message(msg):
        try:
            queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    bus.subscribe(_on_message)

    async def event_stream():
        try:
            # Enviar últimas mensagens do buffer como histórico
            recent = bus.get_messages(limit=limit)
            for msg in recent:
                d = msg.to_dict()
                d["ts"] = msg.timestamp.strftime("%H:%M:%S")
                yield f"data: {_json.dumps(d, ensure_ascii=False)}\n\n"

            # Stream em tempo real
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    d = msg.to_dict()
                    d["ts"] = msg.timestamp.strftime("%H:%M:%S")
                    yield f"data: {_json.dumps(d, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat para manter conexão
                    yield "data: [HEARTBEAT]\n\n"
        finally:
            bus.unsubscribe(_on_message)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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


class CodeRunnerRequest(BaseModel):
    """Request para execução via Code Runner"""
    code: str
    language: str = "python"
    version: str = "3.11"
    stdin: str = ""


@app.post("/code/run")
async def run_code_sandbox(request: CodeRunnerRequest):
    """
    Executa código Python de forma isolada via Code Runner.
    Ideal para executar snippets de código do usuário com segurança.
    """
    from specialized_agents.code_runner_client import get_code_runner_client
    
    client = get_code_runner_client()
    
    # Verifica disponibilidade
    if not await client.is_available():
        raise HTTPException(503, "Code Runner não disponível")
    
    result = await client.execute(
        code=request.code,
        language=request.language,
        version=request.version,
        stdin=request.stdin
    )
    
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "language": result.language,
        "version": result.version
    }


@app.get("/code/runtimes")
async def get_runtimes():
    """Lista runtimes disponíveis no Code Runner"""
    from specialized_agents.code_runner_client import get_code_runner_client
    
    client = get_code_runner_client()
    runtimes = await client.get_runtimes()
    
    return {"runtimes": runtimes}


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


class CommunicationRequest(BaseModel):
    user_id: Optional[str] = "webui_user"
    content: str
    conversation_id: Optional[str] = None
    wait_for_responses: bool = True
    timeout: int = 5
    clarify_to_director: bool = True


@app.post("/communication/send")
async def webui_send(request: CommunicationRequest):
    """Recebe mensagem do Open WebUI, publica no bus e agrega respostas.

    Fluxo:
    - Publica MessageType.REQUEST com `source` = `webui:{user_id}` e `target` = `all`.
    - Se `wait_for_responses` True, escuta respostas por `timeout` segundos.
    - Se nenhuma resposta ou se `clarify_to_director` True quando necessário, encaminha para `DIRETOR`.
    """
    bus = get_communication_bus()
    source = f"webui:{request.user_id}"
    conv_id = request.conversation_id or None

    # Publicar request inicial
    published = bus.publish(
        MessageType.REQUEST,
        source,
        "all",
        request.content,
        {"conversation_id": conv_id} if conv_id else {}
    )

    responses = []

    if request.wait_for_responses and request.timeout > 0:
        loop = asyncio.get_event_loop()

        def _on_message(m):
            try:
                # aceitar mensagens direcionadas ao webui source, ao alvo 'webui' ou broadcasts
                if m.target == source or m.target == "webui" or m.target == "all":
                    # filtro por conversation_id quando disponível
                    if conv_id:
                        if m.metadata.get("conversation_id") == conv_id:
                            responses.append(m.to_dict())
                    else:
                        responses.append(m.to_dict())
            except Exception:
                pass

        bus.subscribe(_on_message)

        try:
            await asyncio.sleep(request.timeout)
        finally:
            bus.unsubscribe(_on_message)

    # Se não houver respostas e for solicitado, encaminhar ao Diretor
    if (not responses) and request.clarify_to_director:
        director_msg = f"Esclarecimento solicitado para: {request.content}"
        bus.publish(
            MessageType.REQUEST,
            "webui_bridge",
            "DIRETOR",
            director_msg,
            {"conversation_id": conv_id} if conv_id else {}
        )

    return {
        "published": published.to_dict() if published else None,
        "responses": responses,
        "responses_count": len(responses)
    }


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
async def send_test_message(message: str = "Mensagem de teste via API", start_responder: bool = False, wait_seconds: float = 0.5):
    """Envia mensagem de teste

    If `start_responder` is True the endpoint will attempt to start
    the lightweight `agent_responder` inside the running process before
    publishing the coordinator message. This is useful for manual tests.

    `wait_seconds` controls how long the endpoint will wait after publishing
    to capture any immediate local response messages from the bus (default 0.5s).
    """
    if start_responder:
        try:
            from specialized_agents.agent_responder import start_responder
            start_responder()
            logger.info("agent_responder started via /communication/test request")
        except Exception:
            logger.exception("Failed to start agent_responder via /communication/test")

    bus = get_communication_bus()

    log_coordinator(message)

    # Optionally wait a short time and return any local responses captured in this process
    if wait_seconds and wait_seconds > 0:
        await asyncio.sleep(wait_seconds)
        responses = [m.to_dict() for m in bus.get_messages(limit=50, message_types=[MessageType.RESPONSE])]
        return {"success": True, "message": "Mensagem de teste enviada", "local_responses_count": len(responses), "local_responses": responses, "subscribers_count": len(bus.subscribers)}

    return {"success": True, "message": "Mensagem de teste enviada"}


class PublishRequest(BaseModel):
    message_type: str
    source: str
    target: str
    content: str
    metadata: Optional[dict] = None


@app.post("/communication/publish")
async def publish_communication_message(request: PublishRequest):
    """Publica uma mensagem arbitrária no bus de comunicação (admin/test)."""
    bus = get_communication_bus()
    try:
        mt = MessageType(request.message_type)
    except Exception:
        mt = MessageType.REQUEST

    msg = bus.publish(
        mt,
        source=request.source,
        target=request.target,
        content=request.content,
        metadata=request.metadata or {}
    )

    return {"success": True, "message_id": msg.id if msg else None}


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


# ================== Confluence Agent Endpoints ==================

@app.get("/confluence/templates")
async def list_confluence_templates():
    """Lista templates de documentação disponíveis"""
    from specialized_agents.confluence_agent import get_confluence_agent
    agent = get_confluence_agent()
    return {
        "templates": agent.list_templates(),
        "count": len(agent.list_templates())
    }


@app.get("/confluence/capabilities")
async def get_confluence_capabilities():
    """Retorna capabilities do Confluence Agent"""
    from specialized_agents.confluence_agent import get_confluence_agent
    agent = get_confluence_agent()
    return agent.get_capabilities()


class ConfluenceDocRequest(BaseModel):
    template: str
    title: Optional[str] = None
    params: Optional[Dict[str, Any]] = {}


@app.post("/confluence/document")
async def create_confluence_document(request: ConfluenceDocRequest):
    """Cria documento a partir de um template"""
    from specialized_agents.confluence_agent import get_confluence_agent
    agent = get_confluence_agent()
    
    try:
        output_path = agent.create_from_template(
            request.template,
            title=request.title,
            **request.params
        )
        
        # Validar conforme Regra 0.2
        validation = agent.validate_page(output_path)
        
        return {
            "success": True,
            "path": output_path,
            "template": request.template,
            "title": request.title,
            "validation": validation
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar documento: {str(e)}")


class ConfluenceGenerateRequest(BaseModel):
    description: str
    doc_type: Optional[str] = "auto"


@app.post("/confluence/generate")
async def generate_confluence_from_description(request: ConfluenceGenerateRequest):
    """
    Gera documento a partir de descrição em linguagem natural.
    Usa Ollama LOCAL para economizar tokens do Copilot.
    """
    from specialized_agents.confluence_agent import get_confluence_agent
    agent = get_confluence_agent()
    
    try:
        output_path = await agent.generate_from_description(
            request.description,
            request.doc_type
        )
        
        validation = agent.validate_page(output_path)
        
        return {
            "success": True,
            "path": output_path,
            "description": request.description,
            "validation": validation,
            "message": "Documento gerado via Ollama LOCAL (economia de tokens)",
            "provider": "ollama_local"
        }
    except Exception as e:
        raise HTTPException(500, f"Erro ao gerar documento: {str(e)}")


@app.get("/confluence/documents")
async def list_confluence_documents():
    """Lista documentos gerados"""
    from pathlib import Path
    docs_dir = Path(__file__).parent / "confluence_docs"
    
    if not docs_dir.exists():
        return {"documents": [], "count": 0}
    
    docs = []
    for f in docs_dir.glob("*.html"):
        docs.append({
            "name": f.stem,
            "filename": f.name,
            "size_kb": round(f.stat().st_size / 1024, 2),
            "modified": f.stat().st_mtime
        })
    
    return {"documents": docs, "count": len(docs)}


@app.get("/confluence/document/{filename}")
async def download_confluence_document(filename: str):
    """Download de documento Confluence"""
    from pathlib import Path
    docs_dir = Path(__file__).parent / "confluence_docs"
    filepath = docs_dir / filename
    
    if not filepath.exists():
        raise HTTPException(404, f"Documento não encontrado: {filename}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/confluence/rules")
async def get_confluence_rules():
    """Retorna regras herdadas do Confluence Agent (auditoria)"""
    from specialized_agents.confluence_agent import get_confluence_agent
    agent = get_confluence_agent()
    return {
        "agent": "ConfluenceAgent",
        "rules": agent.get_rules(),
        "inherited_count": len(agent.get_rules())
    }


# ================== Security Agent Endpoints ==================

class SecurityScanRequest(BaseModel):
    target_path: Optional[str] = None
    extensions: Optional[List[str]] = None
    include_dependencies: bool = True


@app.get("/security/capabilities")
async def get_security_capabilities():
    """Retorna capabilities do Security Agent"""
    from specialized_agents.security_agent import SecurityAgent
    agent = SecurityAgent()
    return agent.capabilities


@app.get("/security/rules")
async def get_security_rules():
    """Retorna regras herdadas do Security Agent (auditoria)"""
    from specialized_agents.security_agent import SecurityAgent
    agent = SecurityAgent()
    return {
        "agent": "SecurityAgent",
        "rules": agent.get_rules(),
        "inherited_count": len(agent.get_rules())
    }


@app.post("/security/scan")
async def run_security_scan(request: SecurityScanRequest):
    """Executa scan de segurança no diretório especificado"""
    from specialized_agents.security_agent import SecurityAgent
    
    agent = SecurityAgent()
    
    # Executar scan de código
    report = agent.scan_directory(
        target_path=request.target_path,
        extensions=request.extensions
    )
    
    # Incluir scan de dependências se solicitado
    if request.include_dependencies:
        dep_vulns = agent.scan_dependencies()
        report.vulnerabilities.extend(dep_vulns)
        report.summary["dependency_vulnerabilities"] = len(dep_vulns)
    
    # Validar conforme Regra 0.2
    validation = agent.validate_scan(report)
    
    return {
        "report": report.to_dict(),
        "validation": validation,
        "deployment_allowed": validation["valid"]
    }


@app.get("/security/scan/{scan_id}/report")
async def get_security_report_markdown(scan_id: str, target_path: Optional[str] = None):
    """Gera relatório de segurança em Markdown"""
    from specialized_agents.security_agent import SecurityAgent
    
    agent = SecurityAgent()
    report = agent.scan_directory(target_path=target_path)
    markdown = agent.generate_report_markdown(report)
    
    return StreamingResponse(
        io.BytesIO(markdown.encode()),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=security_report_{scan_id}.md"}
    )


@app.post("/security/validate")
async def validate_for_deployment(request: SecurityScanRequest):
    """Valida se código está pronto para deploy (sem vulnerabilidades críticas)"""
    from specialized_agents.security_agent import SecurityAgent
    
    agent = SecurityAgent()
    report = agent.scan_directory(target_path=request.target_path)
    validation = agent.validate_scan(report)
    
    return {
        "deployment_allowed": validation["valid"],
        "critical_count": report.summary.get("critical", 0),
        "high_count": report.summary.get("high", 0),
        "blocking_reason": validation.get("blocking_reason"),
        "compliance": report.compliance_status
    }


# ================== Data Agent Endpoints ==================

class PipelineCreateRequest(BaseModel):
    name: str
    description: str = ""


class DataSourceRequest(BaseModel):
    pipeline_id: str
    name: str
    format: str
    path: str
    schema: Optional[Dict[str, str]] = None


@app.get("/data/capabilities")
async def get_data_capabilities():
    """Retorna capabilities do Data Agent"""
    from specialized_agents.data_agent import get_data_agent
    agent = get_data_agent()
    return agent.capabilities


@app.get("/data/rules")
async def get_data_rules():
    """Retorna regras herdadas do Data Agent"""
    from specialized_agents.data_agent import get_data_agent
    agent = get_data_agent()
    return {
        "agent": "DataAgent",
        "rules": agent.get_rules(),
        "inherited_count": len(agent.get_rules())
    }


@app.post("/data/pipeline")
async def create_data_pipeline(request: PipelineCreateRequest):
    """Cria um novo pipeline de dados"""
    from specialized_agents.data_agent import get_data_agent
    agent = get_data_agent()
    pipeline = agent.create_pipeline(request.name, request.description)
    return pipeline.to_dict()


@app.get("/data/pipeline/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Retorna detalhes de um pipeline"""
    from specialized_agents.data_agent import get_data_agent
    agent = get_data_agent()
    if pipeline_id not in agent.pipelines:
        raise HTTPException(status_code=404, detail="Pipeline não encontrado")
    return agent.pipelines[pipeline_id].to_dict()


@app.post("/data/pipeline/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str):
    """Executa um pipeline de dados"""
    from specialized_agents.data_agent import get_data_agent
    agent = get_data_agent()
    try:
        result = agent.run_pipeline(pipeline_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/data/quality/{source_name}")
async def assess_data_quality(source_name: str):
    """Avalia qualidade dos dados de uma fonte"""
    from specialized_agents.data_agent import get_data_agent
    agent = get_data_agent()
    try:
        report = agent.assess_data_quality(source_name)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/data/metrics/{source_name}")
async def get_data_metrics(source_name: str):
    """Gera métricas analíticas de uma fonte de dados"""
    from specialized_agents.data_agent import get_data_agent
    agent = get_data_agent()
    try:
        return agent.generate_metrics(source_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ================== Performance Agent Endpoints ==================

class LoadTestRequest(BaseModel):
    target_url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None
    users: int = 10
    duration_seconds: int = 30
    ramp_up_seconds: int = 5


@app.get("/performance/capabilities")
async def get_performance_capabilities():
    """Retorna capabilities do Performance Agent"""
    from specialized_agents.performance_agent import get_performance_agent
    agent = get_performance_agent()
    return agent.capabilities


@app.get("/performance/rules")
async def get_performance_rules():
    """Retorna regras herdadas do Performance Agent"""
    from specialized_agents.performance_agent import get_performance_agent
    agent = get_performance_agent()
    return {
        "agent": "PerformanceAgent",
        "rules": agent.get_rules(),
        "inherited_count": len(agent.get_rules())
    }


@app.post("/performance/load-test")
async def run_load_test(request: LoadTestRequest, background_tasks: BackgroundTasks):
    """Executa teste de carga em um endpoint"""
    from specialized_agents.performance_agent import get_performance_agent, LoadTestConfig, TestType
    
    agent = get_performance_agent()
    
    config = LoadTestConfig(
        target_url=request.target_url,
        method=request.method,
        headers=request.headers or {},
        body=request.body,
        users=request.users,
        duration_seconds=request.duration_seconds,
        ramp_up_seconds=request.ramp_up_seconds,
        test_type=TestType.LOAD
    )
    
    # Executar teste (pode demorar)
    report = agent.run_load_test(config)
    validation = agent.validate_test(report)
    
    return {
        "report": report.to_dict(),
        "validation": validation,
        "passed": validation["valid"]
    }


@app.get("/performance/report/{test_id}")
async def get_performance_report(test_id: str):
    """Retorna relatório de performance em Markdown"""
    from specialized_agents.performance_agent import get_performance_agent
    
    agent = get_performance_agent()
    report_path = agent.reports_path / f"{test_id}.json"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    
    with open(report_path) as f:
        report_data = json.load(f)
    
    return report_data


@app.post("/performance/baseline/{endpoint}")
async def set_performance_baseline(endpoint: str, test_id: str):
    """Define baseline de performance para um endpoint"""
    from specialized_agents.performance_agent import get_performance_agent
    
    agent = get_performance_agent()
    report_path = agent.reports_path / f"{test_id}.json"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Teste não encontrado")
    
    # Carregar e converter para objeto
    with open(report_path) as f:
        data = json.load(f)
    
    agent.baselines[endpoint] = {
        "test_id": data["test_id"],
        "timestamp": data["completed_at"],
        "metrics": data["metrics"],
        "percentiles": data["percentiles"]
    }
    
    return {"success": True, "endpoint": endpoint, "baseline_test_id": test_id}


@app.get("/performance/regression/{endpoint}")
async def check_performance_regression(endpoint: str, test_id: str):
    """Verifica regressão de performance contra baseline"""
    from specialized_agents.performance_agent import get_performance_agent, PerformanceReport, LoadTestConfig, TestType
    
    agent = get_performance_agent()
    report_path = agent.reports_path / f"{test_id}.json"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Teste não encontrado")
    
    with open(report_path) as f:
        data = json.load(f)
    
    # Criar report object para comparação
    config = LoadTestConfig(
        target_url=data["config"]["target_url"],
        method=data["config"]["method"],
        users=data["config"]["users"],
        duration_seconds=data["config"]["duration_seconds"]
    )
    
    report = PerformanceReport(
        test_id=data["test_id"],
        test_type=TestType(data["test_type"]),
        config=config,
        started_at=data["started_at"],
        completed_at=data["completed_at"],
        total_requests=data["total_requests"],
        successful_requests=data["successful_requests"],
        failed_requests=data["failed_requests"],
        metrics=data["metrics"],
        percentiles=data["percentiles"]
    )
    
    return agent.check_regression(endpoint, report)


# ================== Run ==================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8503)
