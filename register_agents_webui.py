#!/usr/bin/env python3
"""
Script para registrar agentes especializados no Open WebUI como modelos disponíveis.

Uso:
    python3 register_agents_webui.py [--webui-url URL] [--api-url URL]
    
Exemplo:
    python3 register_agents_webui.py --webui-url http://192.168.15.2:3000 --api-url http://localhost:8503
"""

import os
import sys
import json
import httpx
import argparse
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentsWebUIRegistrar:
    """Registra agentes como modelos no Open WebUI"""
    
    def __init__(self, webui_url: str, api_url: str, api_key: Optional[str] = None):
        self.webui_url = webui_url.rstrip('/')
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key or os.getenv("OPENWEBUI_API_KEY", "")
        self.client = httpx.Client(timeout=30.0)
        
    def close(self):
        """Fecha o cliente HTTP"""
        self.client.close()
    
    def _get_webui_headers(self) -> Dict[str, str]:
        """Retorna headers padrão para WebUI"""
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def get_available_agents(self) -> List[Dict[str, Any]]:
        """Busca agentes disponíveis na API"""
        try:
            response = self.client.get(f"{self.api_url}/agents/models")
            if response.status_code == 200:
                data = response.json()
                return data.get("all_models", [])
            else:
                logger.error(f"Erro ao buscar agentes: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Erro ao conectar API: {e}")
            return []
    
    def register_agent_as_model(self, agent: Dict[str, Any]) -> bool:
        """
        Registra um agente como modelo no Open WebUI.
        
        O Open WebUI usa a API /api/models para gerenciar modelos.
        Precisamos criar uma entrada que permita ao usuário selecionar o agente.
        """
        try:
            model_id = agent.get("model", agent.get("name"))
            
            # Preparar dados do modelo
            model_data = {
                "id": model_id,
                "name": agent.get("display_name", agent.get("name")),
                "description": agent.get("description", ""),
                "info": {
                    "url": f"{self.api_url}/v1/chat/completions",
                    "title": agent.get("display_name", agent.get("name")),
                    "imageUrl": None,
                    "meta": {
                        "description": agent.get("description", ""),
                        "capabilities": agent.get("capabilities", []),
                        "group": agent.get("details", {}).get("family", ""),
                    }
                },
                "ollama": {
                    "embedding_model": None,
                    "keep_alive": "5m"
                },
                "owned_by": "eddie-agents"
            }
            
            # Tentar registrar via POST em /api/models (alguns WebUI)
            try:
                headers = self._get_webui_headers()
                response = self.client.post(
                    f"{self.webui_url}/api/v1/models",
                    json=model_data,
                    headers=headers
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"✅ Agente '{model_id}' registrado no WebUI")
                    return True
                else:
                    logger.warning(f"⚠️  Status {response.status_code} ao registrar {model_id}")
                    return False
                    
            except Exception as e:
                logger.debug(f"POST /api/v1/models falhou: {e}")
                
                # Tentar alternativa: registrar via banco de dados interno
                # Isso requer acesso ao container do WebUI
                return self._register_via_docker(model_id, model_data)
            
        except Exception as e:
            logger.error(f"Erro ao registrar agente {agent.get('name')}: {e}")
            return False
    
    def _register_via_docker(self, model_id: str, model_data: Dict[str, Any]) -> bool:
        """
        Registra modelo via docker exec (direto no banco WebUI).
        
        Requer acesso SSH ao homelab ou docker local.
        """
        try:
            import subprocess
            
            cmd = [
                "docker", "exec", "open-webui",
                "python", "-c",
                f"""
import json
import sqlite3
from pathlib import Path

db = sqlite3.connect('/app/backend/data/webui.db')
cursor = db.cursor()

model_json = json.dumps({json.dumps(model_data)})

# Tentar INSERT ou UPDATE
try:
    cursor.execute(
        'INSERT INTO model (id, data) VALUES (?, ?)',
        ('{model_id}', model_json)
    )
    db.commit()
except:
    cursor.execute(
        'UPDATE model SET data = ? WHERE id = ?',
        (model_json, '{model_id}')
    )
    db.commit()
    
db.close()
print("OK")
"""
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and "OK" in result.stdout:
                logger.info(f"✅ Agente '{model_id}' registrado via docker")
                return True
            else:
                logger.warning(f"Docker registration failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.debug(f"Docker registration falhou: {e}")
            return False
    
    def verify_registration(self, model_id: str) -> bool:
        """Verifica se modelo foi registrado"""
        try:
            headers = self._get_webui_headers()
            response = self.client.get(
                f"{self.webui_url}/api/v1/models/{model_id}",
                headers=headers
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def list_webui_models(self) -> List[str]:
        """Lista modelos registrados no WebUI"""
        try:
            headers = self._get_webui_headers()
            response = self.client.get(
                f"{self.webui_url}/api/v1/models",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [m.get("name", m.get("id")) for m in models]
            else:
                logger.warning(f"Erro ao listar modelos WebUI: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Erro ao conectar WebUI: {e}")
            return []
    
    def register_all_agents(self) -> bool:
        """Registra todos os agentes disponíveis"""
        logger.info(f"🔍 Buscando agentes em {self.api_url}...")
        
        agents = self.get_available_agents()
        if not agents:
            logger.error("❌ Nenhum agente encontrado")
            return False
        
        logger.info(f"📦 Encontrados {len(agents)} agentes")
        
        registered = 0
        for agent in agents:
            if self.register_agent_as_model(agent):
                registered += 1
        
        logger.info(f"✅ {registered}/{len(agents)} agentes registrados")
        
        # Verificar registro
        logger.info(f"🔍 Verificando registro no WebUI ({self.webui_url})...")
        webui_models = self.list_webui_models()
        logger.info(f"📊 Modelos no WebUI: {len(webui_models)}")
        for model in webui_models:
            if "agent-" in model or "homelab-" in model:
                logger.info(f"  ✅ {model}")
        
        return registered > 0
    
    def generate_curl_examples(self) -> str:
        """Gera exemplos de CURL para testar agentes"""
        agents = self.get_available_agents()
        
        examples = "# Exemplos de como chamar agentes via API\n\n"
        
        for agent in agents[:3]:  # Mostrar apenas 3 exemplos
            model_id = agent.get("model", agent.get("name"))
            examples += f"""# {agent.get('display_name', model_id)}
curl -X POST {self.api_url}/v1/chat/completions \\
  -H 'Content-Type: application/json' \\
  -d '{{
    "model": "{model_id}",
    "messages": [
      {{"role": "user", "content": "Explique o que você faz"}}
    ],
    "temperature": 0.7
  }}'

"""
        
        return examples


def main():
    parser = argparse.ArgumentParser(
        description="Registra agentes especializados como modelos no Open WebUI"
    )
    parser.add_argument(
        "--webui-url",
        default="http://192.168.15.2:3000",
        help="URL do Open WebUI (default: http://192.168.15.2:3000)"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8503",
        help="URL da API de agentes (default: http://localhost:8503)"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API Key do Open WebUI (opcional)"
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="Listar agentes disponíveis"
    )
    parser.add_argument(
        "--list-webui-models",
        action="store_true",
        help="Listar modelos registrados no WebUI"
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Mostrar exemplos de como chamar agentes"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular registro sem fazer alterações"
    )
    
    args = parser.parse_args()
    
    registrar = AgentsWebUIRegistrar(
        webui_url=args.webui_url,
        api_url=args.api_url,
        api_key=args.api_key
    )
    
    try:
        if args.list_agents:
            logger.info(f"📦 Agentes disponíveis em {args.api_url}:")
            agents = registrar.get_available_agents()
            for agent in agents:
                print(f"  • {agent.get('display_name', agent.get('name'))} ({agent.get('model')})")
                if agent.get('description'):
                    print(f"    └─ {agent.get('description')}")
            return
        
        if args.list_webui_models:
            logger.info(f"📊 Modelos no WebUI ({args.webui_url}):")
            models = registrar.list_webui_models()
            for model in models:
                print(f"  • {model}")
            return
        
        if args.examples:
            examples = registrar.generate_curl_examples()
            print(examples)
            return
        
        # Registrar agentes
        if args.dry_run:
            logger.info("🧪 Modo simulação - verificando conectividade...")
            agents = registrar.get_available_agents()
            logger.info(f"✅ API acessível - {len(agents)} agentes encontrados")
            logger.info("ℹ️  Execute sem --dry-run para registrar agentes")
        else:
            logger.info("🚀 Iniciando registro de agentes...")
            success = registrar.register_all_agents()
            
            if success:
                logger.info(f"""
✅ Registro concluído!

Próximos passos:
1. Acesse Open WebUI em {args.webui_url}
2. Vá para Modelos > Modelos Disponíveis
3. Procure por agentes registrados (agent-python, agent-go, etc)
4. Selecione um agente como modelo padrão
5. Comece a usar!

Para testar via API:
{registrar.generate_curl_examples()}
""")
            else:
                logger.error("❌ Falha ao registrar agentes")
                sys.exit(1)
    
    finally:
        registrar.close()


if __name__ == "__main__":
    main()
