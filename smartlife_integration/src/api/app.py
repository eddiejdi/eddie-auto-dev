"""
SmartLife REST API Application
"""
import structlog
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..core import SmartLifeService

logger = structlog.get_logger()

# Instância global do serviço (será configurada na startup)
smartlife_service: Optional[SmartLifeService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    global smartlife_service
    
    logger.info("Iniciando SmartLife API...")
    
    # O serviço será injetado externamente ou criado aqui
    if smartlife_service:
        await smartlife_service.start()
    
    yield
    
    # Shutdown
    logger.info("Parando SmartLife API...")
    if smartlife_service:
        await smartlife_service.stop()


def create_app(config: dict = None, service: SmartLifeService = None) -> FastAPI:
    """
    Cria e configura a aplicação FastAPI.
    
    Args:
        config: Configuração do sistema
        service: Instância do SmartLifeService (opcional)
    """
    global smartlife_service
    
    if service:
        smartlife_service = service
    
    api_config = config.get("api", {}) if config else {}
    
    app = FastAPI(
        title="SmartLife API",
        description="API REST para controle de dispositivos SmartLife/Tuya",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # CORS
    cors_origins = api_config.get("cors_origins", ["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Middleware de logging
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"Request: {request.method} {request.url.path}")
        response = await call_next(request)
        return response
    
    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "type": type(exc).__name__}
        )
    
    # Importar e incluir rotas
    from .routes import devices, automations, scenes, users
    
    app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
    app.include_router(automations.router, prefix="/api/automations", tags=["Automations"])
    app.include_router(scenes.router, prefix="/api/scenes", tags=["Scenes"])
    app.include_router(users.router, prefix="/api/users", tags=["Users"])
    
    # Rotas base
    @app.get("/", tags=["Health"])
    async def root():
        return {
            "service": "SmartLife API",
            "version": "1.0.0",
            "status": "running"
        }
    
    @app.get("/health", tags=["Health"])
    async def health():
        status = {
            "status": "healthy",
            "service": smartlife_service is not None,
        }
        
        if smartlife_service:
            status["devices_loaded"] = smartlife_service.device_manager is not None
            status["automations_enabled"] = smartlife_service.automation_engine is not None
        
        return status
    
    @app.get("/api/status", tags=["Status"])
    async def api_status():
        """Status completo do sistema."""
        if not smartlife_service:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        return await smartlife_service.get_status()
    
    return app


def get_service() -> SmartLifeService:
    """Retorna a instância do serviço SmartLife."""
    if not smartlife_service:
        raise HTTPException(status_code=503, detail="SmartLife service not initialized")
    return smartlife_service


# Aplicação padrão (para uvicorn)
app = FastAPI(
    title="SmartLife API",
    description="API REST para controle de dispositivos SmartLife/Tuya",
    version="1.0.0"
)


@app.get("/")
async def root():
    return {"message": "SmartLife API - Use /docs para documentação"}


@app.get("/health")
async def health():
    return {"status": "ok"}
