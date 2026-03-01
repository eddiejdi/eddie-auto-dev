#!/usr/bin/env python3
"""
Ponte de integração entre Agentes Especializados e OpenWebUI
Expõe todos os agentes como modelos disponíveis no WebUI
Permite que o WebUI chame agentes via API compatível com Ollama
"""

import os
import httpx
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# URLs de serviços
API_HOST = os.getenv("API_HOST", "http://localhost:8503")
HOMELAB_HOST = os.getenv("HOMELAB_HOST", "192.168.15.2")
HOMELAB_API = os.getenv("HOMELAB_API", f"http://{HOMELAB_HOST}:8503")


@dataclass
class AgentModel:
    """Representa um agente como modelo disponível no WebUI"""
    
    model_id: str  # python, javascript, go, etc
    name: str
    description: str
    capabilities: List[str]
    group: str  # language-agent, specialized-agent
    icon: str  # emoji ou URL
    is_local: bool = True
    is_homelab: bool = False


class AgentsWebUIBridge:
    """
    Ponte de integração entre agentes e OpenWebUI.
    
    # Fluxo:
    1. WebUI lista modelos disponíveis via GET /v1/models (compatível com Ollama API)
    2. WebUI seleciona um agente e faz POST /v1/chat/completions
    3. Bridge roteia para o agente apropriado via API local ou homelab
    4. Agente processa e retorna resposta
    5. Bridge traduz resposta para formato OpenAI/Ollama
    """
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=300.0)
        self._models_cache: List[AgentModel] = []
        self._cache_time: Optional[datetime] = None
        self._local_agents: Dict[str, AgentModel] = {}
        self._homelab_agents: Dict[str, AgentModel] = {}
        
    async def initialize(self):
        """Inicializa bridge (descoberta de agentes será lazy)"""
        # Descoberta será feita sob demanda na primeira chamada a get_available_models()
        # Isso evita problema circular: bridge tenta chamar /agents durante startup
        # mas naquele momento /agents endpoint ainda não está pronto
        logger.info("✅ Agents WebUI Bridge initialized (agent discovery lazy)")
        
    async def close(self):
        """Fecha cliente HTTP"""
        await self.client.aclose()
        
    async def _refresh_agents(self, force: bool = False) -> List[AgentModel]:
        """Atualiza lista de agentes disponíveis"""
        # Cache por 5 minutos
        if not force and self._cache_time:
            from datetime import timedelta
            if datetime.now() - self._cache_time < timedelta(minutes=5):
                return self._models_cache
        
        models = []
        
        # Carregar agentes locais
        try:
            local_agents = await self._get_local_agents()
            models.extend(local_agents)
        except Exception as e:
            logger.warning(f"Erro ao carregar agentes locais: {e}")
        
        # Carregar agentes homelab (remoto)
        try:
            homelab_agents = await self._get_homelab_agents()
            models.extend(homelab_agents)
        except Exception as e:
            logger.debug(f"Homelab não disponível: {e}")
        
        self._models_cache = models
        self._cache_time = datetime.now()
        return models
    
    async def _get_local_agents(self) -> List[AgentModel]:
        """
        Busca agentes locais (DESABILITADO)
        Apenas agentes homelab são utilizados para evitar duplicação
        """
        # Retorna lista vazia - usar apenas agentes homelab
        return []
    
    async def _get_homelab_agents(self) -> List[AgentModel]:
        """
        Busca agentes disponíveis no homelab/servidor remoto
        Se estiver rodando no homelab, usa localhost como primeira opção
        """
        import os
        agents = []
        
        # Detectar se estamos no homelab por username
        is_homelab = os.getenv("LOGNAME") == "homelab" or os.getenv("USER") == "homelab"
        
        # URLs a tentar, ordenadas por prioridade
        # SEMPRE tentar localhost primeiro para buscar agentes locais
        if is_homelab:
            # No homelab, tentar localhost primeiro (API local do homelab)
            urls_to_try = ["http://localhost:8503"]
        else:
            # Local, tentar localhost primeiro (agentes locais), depois homelab
            urls_to_try = ["http://localhost:8503", HOMELAB_API]
        
        for api_url in urls_to_try:
            try:
                logger.debug(f"Tentando descobrir agentes em {api_url}...")
                response = await self.client.get(f"{api_url}/agents", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    available_langs = data.get("available_languages", [])
                    logger.debug(f"  → Encontradas {len(available_langs)} linguagens em {api_url}: {available_langs}")
                    
                    for lang in available_langs:
                        try:
                            info_resp = await self.client.get(f"{api_url}/agents/{lang}", timeout=5.0)
                            if info_resp.status_code == 200:
                                info = info_resp.json()
                                
                                model = AgentModel(
                                    model_id=f"homelab-{lang}",
                                    name=f"🌐 {info.get('name', lang.title())}",
                                    description=f"Agent remoto: {info.get('language', lang)}",
                                    capabilities=info.get("capabilities", []),
                                    group="homelab-agent",
                                    icon="🌐",
                                    is_local=False,
                                    is_homelab=True
                                )
                                self._homelab_agents[lang] = model
                                agents.append(model)
                        except Exception as e:
                            logger.debug(f"Erro ao buscar info de {lang} em {api_url}: {e}")
                    
                    # Se conseguimos agentes, retornar
                    if agents:
                        logger.info(f"✅ Descobertos {len(agents)} agentes em {api_url}")
                        return agents
                    else:
                        logger.warning(f"  → Nenhum agente encontrado em {api_url} (mas /agents respondeu)")
                else:
                    logger.debug(f"  → {api_url}/agents retornou status {response.status_code}")
                        
            except Exception as e:
                logger.debug(f"Erro ao conectar em {api_url}: {e}")
                continue
        
        logger.warning(f"Nenhum agente encontrado - HOMELAB_API={HOMELAB_API}, is_homelab={is_homelab}")
        return agents
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Retorna modelos disponíveis (compatível com Ollama API)"""
        # Se cache está vazio (primeira chamada), forçar refresh
        models = await self._refresh_agents(force=True if len(self._models_cache) == 0 else False)
        return [
            {
                "name": m.model_id,
                "model": m.model_id,
                "display_name": m.name,
                "description": m.description,
                "capabilities": m.capabilities,
                "details": {
                    "family": m.group,
                    "parameter_size": "specialized",
                    "quantization_level": "agent",
                    "context_length": 4096,
                }
            }
            for m in models
        ]
    
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Interface compatível com Ollama para chat via agentes.
        
        Args:
            model: ID do modelo (agent-python, homelab-go, etc)
            messages: Histórico de conversa
            temperature: Température de geração
            max_tokens: Max tokens a gerar
            stream: Se deve fazer streaming
        
        Returns:
            Response compatível com OpenAI/Ollama
        """
        # Extrair linguagem/tipo do model
        if model.startswith("agent-"):
            language = model.replace("agent-", "")
            agent_type = "local"
        elif model.startswith("homelab-"):
            language = model.replace("homelab-", "")
            agent_type = "homelab"
        else:
            raise ValueError(f"Modelo desconhecido: {model}")
        
        # Extrair prompt do último user message
        prompt = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                prompt = msg.get("content", "")
                break
        
        if not prompt:
            raise ValueError("Nenhuma mensagem de usuário encontrada")
        
        # Chamar agente apropriado
        if agent_type == "local":
            return await self._call_local_agent(language, prompt, messages, temperature, max_tokens)
        else:
            return await self._call_homelab_agent(language, prompt, messages, temperature, max_tokens)
    
    async def _call_local_agent(
        self,
        language: str,
        prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Chama agente local"""
        try:
            # Para agora, usamos o atributo do sistema "generate_code" como exemplo
            # Em produção, você pode criar um endpoint que execute tarefas no agente
            payload = {
                "language": language,
                "description": prompt,
                "context": "\n".join([f"{m['role']}: {m['content']}" for m in messages[:-1]])
                if len(messages) > 1 else ""
            }
            
            response = await self.client.post(
                f"{API_HOST}/code/generate",
                json=payload,
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("code", "")
                
                # Formato compatível com Ollama
                return {
                    "model": f"agent-{language}",
                    "created_at": datetime.now().isoformat(),
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "done": True,
                    "total_duration": 0,
                    "load_duration": 0,
                    "prompt_eval_count": len(prompt.split()),
                    "prompt_eval_duration": 0,
                    "eval_count": len(content.split()),
                    "eval_duration": 0,
                }
            else:
                raise Exception(f"API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erro ao chamar agente local {language}: {e}")
            return {
                "model": f"agent-{language}",
                "created_at": datetime.now().isoformat(),
                "message": {
                    "role": "assistant",
                    "content": f"Erro ao processar: {str(e)}"
                },
                "done": True,
            }
    
    async def _call_homelab_agent(
        self,
        language: str,
        prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Chama agente em homelab remoto"""
        try:
            payload = {
                "language": language,
                "description": prompt,
                "context": "\n".join([f"{m['role']}: {m['content']}" for m in messages[:-1]])
                if len(messages) > 1 else ""
            }
            
            response = await self.client.post(
                f"{HOMELAB_API}/code/generate",
                json=payload,
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("code", "")
                
                return {
                    "model": f"homelab-{language}",
                    "created_at": datetime.now().isoformat(),
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "done": True,
                    "location": "homelab"
                }
            else:
                raise Exception(f"Homelab API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erro ao chamar agente homelab {language}: {e}")
            return {
                "model": f"homelab-{language}",
                "created_at": datetime.now().isoformat(),
                "message": {
                    "role": "assistant",
                    "content": f"Erro ao processar no homelab: {str(e)}"
                },
                "done": True,
            }


# Singleton global
_bridge_instance: Optional[AgentsWebUIBridge] = None


def get_agents_webui_bridge() -> AgentsWebUIBridge:
    """Get or create singleton bridge instance"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = AgentsWebUIBridge()
    return _bridge_instance


async def initialize_agents_bridge():
    """Initialize bridge at startup"""
    bridge = get_agents_webui_bridge()
    await bridge.initialize()
