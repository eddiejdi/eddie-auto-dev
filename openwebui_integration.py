#!/usr/bin/env python3
"""
OpenWebUI + Ollama + Telegram Integration Module
Integra todos os modelos disponíveis com Open WebUI e bot Telegram
"""
import os
import httpx
import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


# ============== Configurações ==============
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
OPENWEBUI_HOST = os.getenv("OPENWEBUI_HOST", "http://192.168.15.2:3000")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")  # Token de autenticação

# Modelos especializados para diferentes tarefas
MODEL_PROFILES = {
    "assistant": {
        "model": "eddie-assistant:latest",
        "description": "Assistente pessoal versátil - mensagens, textos, ideias",
        "system_prompt": """Você é Eddie, um assistente pessoal amigável.
Ajude com qualquer tarefa: mensagens, textos, código, ideias.
NUNCA recuse pedidos inofensivos.""",
        "temperature": 0.7,
        "max_tokens": 4096
    },
    "coder": {
        "model": "eddie-coder:latest",
        "description": "Especializado em programação e desenvolvimento",
        "system_prompt": """Você é Eddie, um assistente de programação expert.
Especialidades: Python, JavaScript, TypeScript, Go, Rust, SQL, Docker, Kubernetes.
Sempre forneça código funcional, bem documentado e com boas práticas.
Também pode ajudar com tarefas pessoais quando solicitado.""",
        "temperature": 0.3,
        "max_tokens": 4096
    },
    "homelab": {
        "model": "eddie-homelab:latest",
        "description": "Especializado em homelab e infraestrutura",
        "system_prompt": """Você é Eddie, especialista em homelab e infraestrutura.
Especialidades: Docker, Linux, redes, servidores, automação, monitoramento.
Forneça soluções práticas e comandos funcionais.
Também pode ajudar com tarefas pessoais quando solicitado.""",
        "temperature": 0.4,
        "max_tokens": 4096
    },
    "general": {
        "model": "eddie-assistant:latest",
        "description": "Modelo geral para conversas e perguntas diversas",
        "system_prompt": """Você é um assistente inteligente e prestativo.
Responda de forma clara, concisa e útil em português brasileiro.
Ajude com qualquer tarefa solicitada.""",
        "temperature": 0.7,
        "max_tokens": 2048
    },
    "fast": {
        "model": "qwen2.5-coder:1.5b",
        "description": "Modelo rápido para respostas simples",
        "system_prompt": "Responda de forma direta e concisa.",
        "temperature": 0.5,
        "max_tokens": 1024
    },
    "advanced": {
        "model": "codestral:22b",
        "description": "Modelo avançado para tarefas complexas",
        "system_prompt": """Você é um assistente avançado para tarefas complexas.
Forneça análises detalhadas e soluções completas.""",
        "temperature": 0.5,
        "max_tokens": 8192
    },
    "deepseek": {
        "model": "deepseek-coder-v2:16b",
        "description": "DeepSeek Coder para código complexo",
        "system_prompt": """Você é um expert em programação usando DeepSeek.
Foco em código de alta qualidade e soluções eficientes.""",
        "temperature": 0.3,
        "max_tokens": 4096
    },
    "github": {
        "model": "github-agent:latest",
        "description": "Agente especializado em GitHub e Git",
        "system_prompt": """Você é um agente especializado em GitHub.
Ajude com Git, GitHub Actions, PRs, Issues e automação de repositórios.""",
        "temperature": 0.4,
        "max_tokens": 4096
    },
    "btc_trading": {
        "model": "eddie-assistant:latest",
        "description": "Agente de trading Bitcoin 24/7 - consulta preços, análises e sinais",
        "system_prompt": """Você é um assistente especializado em trading de Bitcoin.
Você tem acesso ao agente de trading que opera 24/7 na KuCoin.
Pode consultar: preço atual, indicadores técnicos (RSI, momentum, volatilidade),
sinais de compra/venda, histórico de trades e performance.
API do agente: http://localhost:8510
Sempre forneça dados atualizados e avisos sobre riscos financeiros.""",
        "temperature": 0.3,
        "max_tokens": 4096,
        "tools": ["btc_price", "btc_analysis", "btc_signal", "btc_trades", "btc_performance"]
    }
}


@dataclass
class ModelInfo:
    """Informações de um modelo"""
    name: str
    size: int
    family: str
    parameter_size: str
    quantization: str
    modified_at: str


@dataclass
class ChatResponse:
    """Resposta de chat"""
    content: str
    model: str
    profile: str
    tokens_used: int
    duration_ms: float
    success: bool
    error: Optional[str] = None


class IntegrationClient:
    """
    Cliente de integração unificado para Ollama e OpenWebUI
    Permite usar modelos via API Ollama ou interface OpenWebUI
    """
    
    def __init__(self):
        self.ollama_url = OLLAMA_HOST
        self.webui_url = OPENWEBUI_HOST
        self.webui_api_key = OPENWEBUI_API_KEY
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout
        self._models_cache: List[ModelInfo] = []
        self._cache_time: Optional[datetime] = None
        self._current_profile = "general"
        
    async def close(self):
        """Fecha o cliente HTTP"""
        await self.client.aclose()
    
    # ============== Gestão de Modelos ==============
    
    async def list_ollama_models(self, force_refresh: bool = False) -> List[ModelInfo]:
        """Lista modelos disponíveis no Ollama"""
        # Cache por 5 minutos
        if not force_refresh and self._cache_time:
            if (datetime.now() - self._cache_time).seconds < 300:
                return self._models_cache
        
        try:
            response = await self.client.get(f"{self.ollama_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = []
                for m in data.get("models", []):
                    details = m.get("details", {})
                    models.append(ModelInfo(
                        name=m.get("name", ""),
                        size=m.get("size", 0),
                        family=details.get("family", "unknown"),
                        parameter_size=details.get("parameter_size", ""),
                        quantization=details.get("quantization_level", ""),
                        modified_at=m.get("modified_at", "")
                    ))
                self._models_cache = models
                self._cache_time = datetime.now()
                return models
        except Exception as e:
            print(f"[Integration] Erro listando modelos: {e}")
        
        return self._models_cache if self._models_cache else []
    
    async def get_model_names(self) -> List[str]:
        """Retorna lista de nomes de modelos"""
        models = await self.list_ollama_models()
        return [m.name for m in models]
    
    async def model_exists(self, model_name: str) -> bool:
        """Verifica se modelo existe"""
        models = await self.get_model_names()
        return model_name in models or model_name.split(":")[0] in [m.split(":")[0] for m in models]
    
    # ============== Perfis de Modelo ==============
    
    def get_profile(self, profile_name: str) -> Dict[str, Any]:
        """Obtém configuração de um perfil"""
        return MODEL_PROFILES.get(profile_name, MODEL_PROFILES["general"])
    
    def list_profiles(self) -> Dict[str, str]:
        """Lista perfis disponíveis com descrições"""
        return {name: p["description"] for name, p in MODEL_PROFILES.items()}
    
    def set_profile(self, profile_name: str) -> bool:
        """Define perfil atual"""
        if profile_name in MODEL_PROFILES:
            self._current_profile = profile_name
            return True
        return False
    
    def get_current_profile(self) -> str:
        """Retorna perfil atual"""
        return self._current_profile
    
    async def auto_select_profile(self, prompt: str) -> str:
        """Seleciona automaticamente o melhor perfil baseado no prompt"""
        prompt_lower = prompt.lower()
        
        # Palavras-chave para cada perfil
        keywords = {
            "coder": ["código", "code", "função", "function", "programa", "script", 
                     "python", "javascript", "typescript", "api", "debug", "erro",
                     "bug", "implementar", "desenvolver", "class", "def "],
            "homelab": ["docker", "container", "servidor", "server", "linux", "ubuntu",
                       "nginx", "proxy", "network", "rede", "ssh", "deploy", "ci/cd",
                       "kubernetes", "k8s", "ansible", "terraform"],
            "github": ["git", "github", "commit", "push", "pull", "merge", "branch",
                      "repository", "repo", "fork", "clone", "pr", "issue", "action"],
            "btc_trading": ["bitcoin", "btc", "preço", "trading", "trade", "comprar", 
                           "vender", "cripto", "crypto", "mercado", "sinal", "rsi",
                           "indicador", "kucoin", "exchange"],
            "fast": ["rápido", "simples", "quick", "simple", "olá", "oi", "hello"],
            "advanced": ["complexo", "avançado", "detalhado", "análise profunda",
                        "arquitetura", "design pattern"]
        }
        
        # Contar matches
        scores = {profile: 0 for profile in keywords}
        for profile, words in keywords.items():
            for word in words:
                if word in prompt_lower:
                    scores[profile] += 1
        
        # Retornar perfil com maior score ou general
        best_profile = max(scores, key=scores.get)
        if scores[best_profile] > 0:
            return best_profile
        
        return "general"
    
    # ============== Chat Ollama ==============
    
    async def chat_ollama(
        self,
        prompt: str,
        profile: str = None,
        model: str = None,
        system: str = None,
        context: List[Dict] = None,
        temperature: float = None,
        max_tokens: int = None,
        stream: bool = False
    ) -> ChatResponse:
        """
        Chat com modelo Ollama
        
        Args:
            prompt: Mensagem do usuário
            profile: Perfil a usar (auto se None)
            model: Modelo específico (sobrescreve perfil)
            system: System prompt (sobrescreve perfil)
            context: Histórico de conversa
            temperature: Temperatura (sobrescreve perfil)
            max_tokens: Max tokens (sobrescreve perfil)
            stream: Se deve fazer streaming
        """
        # Auto-selecionar perfil se não especificado
        if not profile:
            profile = await self.auto_select_profile(prompt)
        
        profile_config = self.get_profile(profile)
        
        # Usar parâmetros do perfil ou sobrescritos
        model_name = model or profile_config["model"]
        system_prompt = system or profile_config["system_prompt"]
        temp = temperature if temperature is not None else profile_config["temperature"]
        tokens = max_tokens or profile_config["max_tokens"]
        
        # Verificar se modelo existe
        if not await self.model_exists(model_name):
            # Fallback para modelo geral
            model_name = MODEL_PROFILES["general"]["model"]
        
        # Construir mensagens
        messages = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})
        
        try:
            start_time = datetime.now()
            
            response = await self.client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": messages,
                    "system": system_prompt,
                    "stream": stream,
                    "options": {
                        "temperature": temp,
                        "num_predict": tokens
                    }
                }
            )
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                data = response.json()
                return ChatResponse(
                    content=data.get("message", {}).get("content", ""),
                    model=model_name,
                    profile=profile,
                    tokens_used=data.get("eval_count", 0),
                    duration_ms=duration_ms,
                    success=True
                )
            else:
                return ChatResponse(
                    content="",
                    model=model_name,
                    profile=profile,
                    tokens_used=0,
                    duration_ms=duration_ms,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return ChatResponse(
                content="",
                model=model_name,
                profile=profile,
                tokens_used=0,
                duration_ms=0,
                success=False,
                error=str(e)
            )
    
    async def generate_ollama(
        self,
        prompt: str,
        profile: str = None,
        model: str = None,
        system: str = None
    ) -> ChatResponse:
        """Geração simples (sem chat/contexto)"""
        if not profile:
            profile = await self.auto_select_profile(prompt)
        
        profile_config = self.get_profile(profile)
        model_name = model or profile_config["model"]
        system_prompt = system or profile_config["system_prompt"]
        
        try:
            start_time = datetime.now()
            
            response = await self.client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": profile_config["temperature"],
                        "num_predict": profile_config["max_tokens"]
                    }
                }
            )
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                data = response.json()
                return ChatResponse(
                    content=data.get("response", ""),
                    model=model_name,
                    profile=profile,
                    tokens_used=data.get("eval_count", 0),
                    duration_ms=duration_ms,
                    success=True
                )
            else:
                return ChatResponse(
                    content="",
                    model=model_name,
                    profile=profile,
                    tokens_used=0,
                    duration_ms=duration_ms,
                    success=False,
                    error=f"HTTP {response.status_code}"
                )
                
        except Exception as e:
            return ChatResponse(
                content="",
                model=model_name,
                profile=profile,
                tokens_used=0,
                duration_ms=0,
                success=False,
                error=str(e)
            )
    
    # ============== Open WebUI ==============
    
    async def check_webui_status(self) -> Dict[str, Any]:
        """Verifica status do Open WebUI"""
        try:
            response = await self.client.get(
                f"{self.webui_url}/api/health",
                timeout=5.0
            )
            return {
                "online": response.status_code == 200,
                "status_code": response.status_code
            }
        except Exception as e:
            return {
                "online": False,
                "error": str(e)
            }
    
    async def chat_webui(
        self,
        prompt: str,
        model: str = None,
        conversation_id: str = None
    ) -> ChatResponse:
        """
        Chat via API do Open WebUI
        Requer autenticação configurada
        """
        if not self.webui_api_key:
            return ChatResponse(
                content="",
                model=model or "unknown",
                profile="webui",
                tokens_used=0,
                duration_ms=0,
                success=False,
                error="API Key do Open WebUI não configurada"
            )
        
        headers = {
            "Authorization": f"Bearer {self.webui_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            start_time = datetime.now()
            
            # Endpoint de chat do Open WebUI
            response = await self.client.post(
                f"{self.webui_url}/api/chat/completions",
                headers=headers,
                json={
                    "model": model or "eddie-coder:latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }
            )
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                data = response.json()
                content = ""
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content", "")
                
                return ChatResponse(
                    content=content,
                    model=model or "unknown",
                    profile="webui",
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                    duration_ms=duration_ms,
                    success=True
                )
            else:
                return ChatResponse(
                    content="",
                    model=model or "unknown",
                    profile="webui",
                    tokens_used=0,
                    duration_ms=duration_ms,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return ChatResponse(
                content="",
                model=model or "unknown",
                profile="webui",
                tokens_used=0,
                duration_ms=0,
                success=False,
                error=str(e)
            )
    
    # ============== Métodos de Conveniência ==============
    
    async def ask(
        self,
        prompt: str,
        use_webui: bool = False,
        profile: str = None,
        context: List[Dict] = None
    ) -> str:
        """
        Método simples para fazer perguntas
        Retorna apenas o texto da resposta
        """
        if use_webui:
            response = await self.chat_webui(prompt)
        else:
            response = await self.chat_ollama(prompt, profile=profile, context=context)
        
        if response.success:
            return response.content
        else:
            return f"Erro: {response.error}"
    
    async def code(self, description: str, language: str = "python") -> str:
        """Gera código usando o perfil coder"""
        prompt = f"Gere código {language} para: {description}\n\nRetorne apenas o código, sem explicações."
        response = await self.chat_ollama(prompt, profile="coder")
        return response.content if response.success else f"Erro: {response.error}"
    
    async def explain(self, code: str, language: str = "python") -> str:
        """Explica código"""
        prompt = f"Explique o seguinte código {language}:\n\n```{language}\n{code}\n```"
        response = await self.chat_ollama(prompt, profile="coder")
        return response.content if response.success else f"Erro: {response.error}"
    
    async def fix_code(self, code: str, error: str, language: str = "python") -> str:
        """Corrige código com erro"""
        prompt = f"""Corrija o seguinte código {language} que está dando erro:

Código:
```{language}
{code}
```

Erro:
```
{error}
```

Retorne o código corrigido e uma breve explicação do que foi corrigido."""
        response = await self.chat_ollama(prompt, profile="coder")
        return response.content if response.success else f"Erro: {response.error}"
    
    # ============== Bitcoin Trading Agent ==============
    
    def query_btc_agent(self, question: str) -> str:
        """
        Consulta o agente de trading de Bitcoin
        
        Args:
            question: Pergunta sobre BTC, preço, análise, sinais, etc.
        
        Returns:
            Resposta do agente de trading
        """
        import subprocess
        try:
            result = subprocess.run(
                ["python3", "/home/home-lab/myClaude/btc_trading_agent/btc_query.py", question],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"❌ Erro: {result.stderr}"
        except Exception as e:
            return f"❌ Erro ao consultar agente: {e}"
    
    def get_btc_price(self) -> str:
        """Obtém preço atual do Bitcoin"""
        return self.query_btc_agent("preço")
    
    def get_btc_analysis(self) -> str:
        """Obtém análise técnica do Bitcoin"""
        return self.query_btc_agent("análise")
    
    def get_btc_signal(self) -> str:
        """Obtém sinal de trading do Bitcoin"""
        return self.query_btc_agent("sinal")
    
    # ============== Embedding ==============
    
    async def get_embedding(self, text: str) -> List[float]:
        """Obtém embedding de texto usando nomic-embed-text"""
        try:
            response = await self.client.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text:latest",
                    "prompt": text
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])
        except Exception as e:
            print(f"[Integration] Erro obtendo embedding: {e}")
        
        return []
    
    # ============== Status ==============
    
    async def get_full_status(self) -> Dict[str, Any]:
        """Retorna status completo da integração"""
        ollama_online = False
        webui_status = await self.check_webui_status()
        models = []
        
        try:
            response = await self.client.get(f"{self.ollama_url}/api/tags", timeout=5.0)
            ollama_online = response.status_code == 200
            if ollama_online:
                models = await self.get_model_names()
        except:
            pass
        
        return {
            "ollama": {
                "online": ollama_online,
                "url": self.ollama_url,
                "models_count": len(models),
                "models": models
            },
            "openwebui": {
                "online": webui_status.get("online", False),
                "url": self.webui_url,
                "authenticated": bool(self.webui_api_key)
            },
            "profiles": {
                "available": list(MODEL_PROFILES.keys()),
                "current": self._current_profile
            },
            "timestamp": datetime.now().isoformat()
        }


# ============== Instância Global ==============
_integration_client: Optional[IntegrationClient] = None


def get_integration_client() -> IntegrationClient:
    """Obtém instância global do cliente de integração"""
    global _integration_client
    if _integration_client is None:
        _integration_client = IntegrationClient()
    return _integration_client


async def close_integration():
    """Fecha cliente global"""
    global _integration_client
    if _integration_client:
        await _integration_client.close()
        _integration_client = None


# ============== Exemplo de Uso ==============
async def demo():
    """Demonstração das funcionalidades"""
    client = get_integration_client()
    
    print("=== Status da Integração ===")
    status = await client.get_full_status()
    print(json.dumps(status, indent=2, default=str))
    
    print("\n=== Perfis Disponíveis ===")
    for name, desc in client.list_profiles().items():
        print(f"  • {name}: {desc}")
    
    print("\n=== Teste de Chat ===")
    response = await client.chat_ollama("Olá! Como você está?", profile="fast")
    print(f"Resposta: {response.content[:200]}")
    print(f"Modelo: {response.model}, Perfil: {response.profile}")
    print(f"Tokens: {response.tokens_used}, Tempo: {response.duration_ms:.0f}ms")
    
    print("\n=== Teste de Código ===")
    code = await client.code("uma função que calcula fibonacci")
    print(f"Código gerado:\n{code[:500]}")
    
    await close_integration()


if __name__ == "__main__":
    asyncio.run(demo())
