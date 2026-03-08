"""
Google Home Integration
Controla dispositivos SmartLife vinculados ao Google Home
"""
import os
import json
import asyncio
import structlog
from pathlib import Path
from typing import Optional, Dict, Any, List

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = structlog.get_logger()

# Escopos necessários para controlar dispositivos
SCOPES = [
    'https://www.googleapis.com/auth/homegraph',
    'https://www.googleapis.com/auth/assistant-sdk-prototype'
]


class GoogleHomeClient:
    """
    Cliente para controlar dispositivos via Google Home.
    Usa a API Home Graph para controle de smart home.
    """
    
    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token_home.json"
    ):
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.creds: Optional[Credentials] = None
        self.service = None
        self._devices: Dict[str, Dict[str, Any]] = {}
    
    async def authenticate(self) -> bool:
        """Autentica com o Google."""
        try:
            # Verificar se já tem token salvo
            if self.token_file.exists():
                self.creds = Credentials.from_authorized_user_file(
                    str(self.token_file), SCOPES
                )
            
            # Se não tem credenciais válidas, fazer autenticação
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not self.credentials_file.exists():
                        logger.error(f"Arquivo de credenciais não encontrado: {self.credentials_file}")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), SCOPES
                    )
                    self.creds = flow.run_local_server(port=8888)
                
                # Salvar token
                with open(self.token_file, 'w') as f:
                    f.write(self.creds.to_json())
            
            logger.info("Autenticação Google Home bem-sucedida")
            return True
            
        except Exception as e:
            logger.error(f"Erro na autenticação: {e}")
            return False
    
    async def get_devices(self) -> List[Dict[str, Any]]:
        """Lista dispositivos vinculados ao Google Home."""
        # Nota: A Home Graph API requer Service Account para algumas operações
        # Para uso pessoal, vamos usar uma abordagem diferente
        
        if not self.creds:
            await self.authenticate()
        
        try:
            # Tentar via Home Graph
            service = build('homegraph', 'v1', credentials=self.creds)
            
            # Request sync para obter dispositivos
            result = service.devices().query(
                body={"agentUserId": "user123"}
            ).execute()
            
            return result.get('devices', [])
            
        except Exception as e:
            logger.warning(f"Home Graph não disponível: {e}")
            # Fallback: retornar dispositivos em cache
            return list(self._devices.values())
    
    async def execute_command(
        self,
        device_id: str,
        command: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Executa comando em um dispositivo.
        
        Args:
            device_id: ID do dispositivo
            command: Comando (OnOff, Brightness, FanSpeed, etc.)
            params: Parâmetros do comando
        """
        if not self.creds:
            await self.authenticate()
        
        try:
            service = build('homegraph', 'v1', credentials=self.creds)
            
            # Construir request de execução
            execution = {
                "command": f"action.devices.commands.{command}",
                "params": params or {}
            }
            
            result = service.devices().executeCommand(
                body={
                    "agentUserId": "user123",
                    "inputs": [{
                        "intent": "action.devices.EXECUTE",
                        "payload": {
                            "commands": [{
                                "devices": [{"id": device_id}],
                                "execution": [execution]
                            }]
                        }
                    }]
                }
            ).execute()
            
            return {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"Erro ao executar comando: {e}")
            return {"success": False, "error": str(e)}


class SmartLifeViaAssistant:
    """
    Controla SmartLife usando comandos de voz do Google Assistant.
    Abordagem alternativa quando Home Graph não está disponível.
    """
    
    def __init__(self):
        self.assistant_url = "https://embeddedassistant.googleapis.com"
    
    async def send_command(self, text_command: str) -> Dict[str, Any]:
        """
        Envia comando de texto para o Google Assistant.
        
        Ex: "Ligue a luz da sala", "Aumente o ventilador do escritório"
        """
        # Esta funcionalidade requer Google Assistant SDK configurado
        # Por enquanto, retorna placeholder
        return {
            "success": False,
            "error": "Google Assistant SDK não configurado",
            "suggestion": "Use: pip install google-assistant-sdk[samples]"
        }


# Script de teste direto
async def test_google_home():
    """Testa integração com Google Home."""
    print("=" * 50)
    print("Teste de Integração Google Home")
    print("=" * 50)
    
    # Verificar credenciais
    creds_file = Path("/home/shared/myClaude/credentials.json")
    if not creds_file.exists():
        print("❌ credentials.json não encontrado")
        return
    
    print(f"✅ Credenciais encontradas: {creds_file}")
    
    # Tentar autenticação
    client = GoogleHomeClient(
        credentials_file=str(creds_file),
        token_file="/home/shared/myClaude/smartlife_integration/token_home.json"
    )
    
    print("\n🔐 Autenticando com Google...")
    success = await client.authenticate()
    
    if success:
        print("✅ Autenticação bem-sucedida!")
        
        print("\n📱 Buscando dispositivos...")
        devices = await client.get_devices()
        print(f"Encontrados {len(devices)} dispositivos")
        
        for device in devices:
            print(f"  - {device.get('name', 'Unknown')}: {device.get('id')}")
    else:
        print("❌ Falha na autenticação")


if __name__ == "__main__":
    asyncio.run(test_google_home())
