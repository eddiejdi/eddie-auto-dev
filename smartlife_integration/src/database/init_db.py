"""
SmartLife Database Initialization
"""
import asyncio
import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)

from .models import Base

logger = structlog.get_logger()

# Global engine e session factory
_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker] = None


def get_database_url(config: dict) -> str:
    """Constrói URL de conexão do database."""
    db_config = config.get("database", {})
    db_type = db_config.get("type", "postgresql")
    
    if db_type == "sqlite":
        # SQLite para desenvolvimento/teste
        db_path = db_config.get("path", "smartlife.db")
        return f"sqlite+aiosqlite:///{db_path}"
    
    elif db_type == "postgresql":
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432)
        name = db_config.get("name", "smartlife")
        user = db_config.get("user", "eddie")
        password = db_config.get("password", "")
        
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
    
    else:
        raise ValueError(f"Database type não suportado: {db_type}")


async def init_database(config: dict) -> AsyncEngine:
    """
    Inicializa o database e cria as tabelas.
    
    Args:
        config: Configuração do sistema
        
    Returns:
        Engine do SQLAlchemy
    """
    global _engine, _async_session_factory
    
    database_url = get_database_url(config)
    logger.info(f"Conectando ao database: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    # Criar engine
    _engine = create_async_engine(
        database_url,
        echo=config.get("database", {}).get("debug", False),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )
    
    # Criar session factory
    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Criar tabelas
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database inicializado com sucesso")
    return _engine


async def close_database():
    """Fecha conexão com o database."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("Conexão com database fechada")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager para obter sessão do database.
    
    Usage:
        async with get_db_session() as session:
            # usar session
    """
    global _async_session_factory
    
    if not _async_session_factory:
        raise RuntimeError("Database não inicializado. Chame init_database() primeiro.")
    
    session = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session() -> AsyncSession:
    """
    Retorna uma sessão do database.
    Lembre-se de fechar a sessão após o uso.
    """
    global _async_session_factory
    
    if not _async_session_factory:
        raise RuntimeError("Database não inicializado. Chame init_database() primeiro.")
    
    return _async_session_factory()


class DatabaseManager:
    """
    Gerenciador de database para uso em classes de serviço.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._initialized = False
    
    async def initialize(self) -> None:
        """Inicializa o database."""
        if self._initialized:
            return
        
        await init_database(self.config)
        self._initialized = True
    
    async def close(self) -> None:
        """Fecha o database."""
        if not self._initialized:
            return
        
        await close_database()
        self._initialized = False
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Obtém uma sessão do database."""
        if not self._initialized:
            await self.initialize()
        
        async with get_db_session() as session:
            yield session


# Script de inicialização standalone
async def main():
    """Script para criar o database."""
    import yaml
    import os
    
    # Carregar config
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        # Config padrão para desenvolvimento
        config = {
            "database": {
                "type": "sqlite",
                "path": "smartlife.db"
            }
        }
    
    print("=" * 50)
    print("SmartLife - Database Initialization")
    print("=" * 50)
    
    try:
        engine = await init_database(config)
        print("✅ Database criado com sucesso!")
        print("📊 Tabelas criadas:")
        
        async with engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: Base.metadata.tables.keys()
            )
            for table in tables:
                print(f"   - {table}")
        
        await close_database()
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
