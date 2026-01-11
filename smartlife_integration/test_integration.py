#!/usr/bin/env python3
"""
SmartLife Integration - Teste Rápido
Verifica se todos os componentes estão funcionando
"""
import asyncio
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent))


async def test_imports():
    """Testa se todos os módulos importam corretamente."""
    print("\n🔍 Testando imports...")
    
    try:
        from src.core import SmartLifeService, DeviceManager, AutomationEngine
        print("  ✅ Core modules OK")
    except ImportError as e:
        print(f"  ❌ Core modules FAILED: {e}")
        return False
    
    try:
        from src.database import init_database, get_db_session
        from src.database.models import Device, User, Automation
        from src.database.repository import DeviceRepository, UserRepository
        print("  ✅ Database modules OK")
    except ImportError as e:
        print(f"  ❌ Database modules FAILED: {e}")
        return False
    
    try:
        from src.integrations.tuya_local import TuyaLocalClient
        from src.integrations.tuya_cloud import TuyaCloudClient
        print("  ✅ Integration modules OK")
    except ImportError as e:
        print(f"  ❌ Integration modules FAILED: {e}")
        return False
    
    try:
        from src.interfaces import SmartLifeTelegramBot
        print("  ✅ Interface modules OK")
    except ImportError as e:
        print(f"  ❌ Interface modules FAILED: {e}")
        return False
    
    try:
        from src.api.app import create_app
        print("  ✅ API modules OK")
    except ImportError as e:
        print(f"  ❌ API modules FAILED: {e}")
        return False
    
    return True


async def test_database():
    """Testa inicialização do banco de dados."""
    print("\n🗄️  Testando database...")
    
    try:
        from src.database.init_db import init_database, close_database
        
        # Usar SQLite para teste
        config = {
            "database": {
                "type": "sqlite",
                "path": "test_smartlife.db"
            }
        }
        
        engine = await init_database(config)
        print("  ✅ Database inicializado")
        
        await close_database()
        print("  ✅ Database fechado")
        
        # Limpar arquivo de teste
        Path("test_smartlife.db").unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        print(f"  ❌ Database FAILED: {e}")
        return False


async def test_tuya_client():
    """Testa cliente Tuya (sem conexão real)."""
    print("\n📱 Testando Tuya Client...")
    
    try:
        from src.integrations.tuya_local import TuyaLocalClient
        
        client = TuyaLocalClient(devices_file="config/devices.json")
        print("  ✅ TuyaLocalClient criado")
        
        from src.integrations.tuya_cloud import TuyaCloudClient
        
        cloud = TuyaCloudClient(
            api_key="test_key",
            api_secret="test_secret",
            region="eu"
        )
        print("  ✅ TuyaCloudClient criado")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Tuya Client FAILED: {e}")
        return False


async def test_api():
    """Testa criação da API FastAPI."""
    print("\n🌐 Testando API...")
    
    try:
        from src.api.app import create_app
        
        config = {
            "api": {
                "host": "0.0.0.0",
                "port": 8100
            }
        }
        
        app = create_app(config)
        print(f"  ✅ FastAPI app criado: {app.title}")
        
        # Verificar rotas
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        print(f"  ✅ {len(routes)} rotas registradas")
        
        return True
        
    except Exception as e:
        print(f"  ❌ API FAILED: {e}")
        return False


async def test_service():
    """Testa criação do serviço principal."""
    print("\n🚀 Testando SmartLife Service...")
    
    try:
        from src.core import SmartLifeService
        
        config = {
            "tuya": {
                "api_key": "test",
                "api_secret": "test",
                "region": "eu"
            },
            "local": {
                "enabled": False
            },
            "telegram": {
                "enabled": False
            }
        }
        
        service = SmartLifeService(config)
        print("  ✅ SmartLifeService criado")
        
        return True
        
    except Exception as e:
        print(f"  ❌ SmartLifeService FAILED: {e}")
        return False


async def main():
    """Executa todos os testes."""
    print("=" * 50)
    print("   SmartLife Integration - Teste")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", await test_imports()))
    results.append(("Database", await test_database()))
    results.append(("Tuya Client", await test_tuya_client()))
    results.append(("API", await test_api()))
    results.append(("Service", await test_service()))
    
    print("\n" + "=" * 50)
    print("   Resultado dos Testes")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-" * 50)
    print(f"  Total: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
