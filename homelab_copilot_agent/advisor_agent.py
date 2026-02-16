#!/usr/bin/env python3
"""
Homelab Advisor Agent
Consultor especialista para o servidor homelab conectado ao barramento
"""
import os
import sys
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Optional, List, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
import psutil
import subprocess
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Adicionar path para imports do projeto principal
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
    from tools.agent_ipc import publish_request, poll_response, fetch_pending, respond, init_table
    BUS_AVAILABLE = True
except ImportError:
    BUS_AVAILABLE = False
    print("⚠️  Bus/IPC não disponível - modo standalone")


app = FastAPI(title="Homelab Advisor Agent", version="1.0.0")

# ==================== Prometheus Metrics ====================
http_requests_total = Counter(
    "http_requests_total",
    "Total de requisições HTTP",
    ["endpoint", "method", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP em segundos",
    ["endpoint", "method"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

advisor_analysis_total = Counter(
    "advisor_analysis_total",
    "Total de análises completadas",
    ["scope"]
)

advisor_analysis_duration_seconds = Histogram(
    "advisor_analysis_duration_seconds",
    "Duração das análises em segundos",
    ["scope"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

advisor_agents_trained_total = Counter(
    "advisor_agents_trained_total",
    "Total de agentes treinados",
    ["agent_name"]
)

advisor_ipc_pending_requests = Gauge(
    "advisor_ipc_pending_requests",
    "Número de requisições IPC pendentes"
)

advisor_llm_calls_total = Counter(
    "advisor_llm_calls_total",
    "Total de chamadas ao LLM",
    ["status"]
)

advisor_llm_duration_seconds = Histogram(
    "advisor_llm_duration_seconds",
    "Duração das chamadas ao LLM em segundos",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 90.0)
)


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 256
    model: Optional[str] = None


class AnalysisRequest(BaseModel):
    scope: str  # "performance", "security", "safeguards", "architecture"
    context: Optional[Dict[str, Any]] = None


class TrainingRequest(BaseModel):
    agent_name: str
    task_description: str
    solution: str
    metadata: Optional[Dict[str, Any]] = None


# ==================== HTTP Middleware ====================
@app.middleware("http")
async def http_middleware(request: Request, call_next):
    """Middleware para registrar requisições HTTP com Prometheus"""
    start_time = time.time()
    endpoint = request.url.path
    method = request.method
    
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as exc:
        status = 500
        raise
    finally:
        duration = time.time() - start_time
        http_requests_total.labels(endpoint=endpoint, method=method, status=status).inc()
        http_request_duration_seconds.labels(endpoint=endpoint, method=method).observe(duration)
    
    return response


class HomelabAdvisor:
    """Consultor especializado no ambiente homelab"""
    
    def __init__(self):
        self.ollama_host = os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "eddie-homelab:latest")
        self.database_url = os.environ.get("DATABASE_URL")
        self.bus = get_communication_bus() if BUS_AVAILABLE else None
        
        # Inicializar IPC
        if self.database_url:
            try:
                init_table()
                print("✅ IPC table initialized")
            except Exception as e:
                print(f"⚠️  IPC init failed: {e}")
        
        # Subscriber do bus
        if self.bus:
            self.bus.subscribe(self.handle_bus_message)
            print("✅ Subscribed to communication bus")
    
    async def call_llm(self, prompt: str, max_tokens: int = 512) -> str:
        """Chama LLM para análise/recomendações"""
        start_time = time.time()
        try:
            url = f"{self.ollama_host}/api/generate"
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens}
            }
            async with httpx.AsyncClient(timeout=180.0) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                advisor_llm_calls_total.labels(status="success").inc()
                return data.get("response", "")
        except Exception as exc:
            advisor_llm_calls_total.labels(status="error").inc()
            err_type = type(exc).__name__
            print(f"⚠️  LLM error ({err_type}): {exc}")
            return f"[erro LLM ({err_type}): {exc}]"
        finally:
            duration = time.time() - start_time
            advisor_llm_duration_seconds.observe(duration)
    
    async def analyze_performance(self, context: Dict = None) -> Dict[str, Any]:
        """Analisa performance do sistema"""
        start_time = time.time()
        try:
            # Coletar métricas
            cpu_percent = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": mem.percent,
                "memory_available_gb": mem.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3)
            }
            
            # Construir prompt para LLM
            prompt = f"""Você é um consultor de performance de servidores homelab.

Métricas atuais:
- CPU: {cpu_percent}%
- Memória: {mem.percent}% ({mem.available / (1024**3):.1f}GB livres)
- Disco: {disk.percent}% ({disk.free / (1024**3):.1f}GB livres)

Forneça recomendações específicas de otimização de performance."""
            
            recommendations = await self.call_llm(prompt, max_tokens=400)
            
            return {
                "metrics": metrics,
                "recommendations": recommendations,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            duration = time.time() - start_time
            advisor_analysis_total.labels(scope="performance").inc()
            advisor_analysis_duration_seconds.labels(scope="performance").observe(duration)
    
    async def analyze_security(self, context: Dict = None) -> Dict[str, Any]:
        """Analisa segurança e sugere safeguards"""
        start_time = time.time()
        try:
            # Verificar portas abertas
            try:
                result = subprocess.run(
                    ['ss', '-tuln'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                open_ports = result.stdout
            except Exception:
                open_ports = "Não foi possível listar portas"
            
            prompt = f"""Você é um consultor de segurança de servidores homelab.

Portas abertas detectadas:
{open_ports[:500]}

Analise e forneça:
1. Riscos de segurança identificados
2. Safeguards recomendados
3. Configurações de firewall sugeridas"""
            
            recommendations = await self.call_llm(prompt, max_tokens=500)
            
            return {
                "recommendations": recommendations,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            duration = time.time() - start_time
            advisor_analysis_total.labels(scope="security").inc()
            advisor_analysis_duration_seconds.labels(scope="security").observe(duration)
    
    async def review_architecture(self, context: Dict = None) -> Dict[str, Any]:
        """Revisa arquitetura do sistema"""
        # Listar containers Docker
        try:
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}:{{.Status}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            containers = result.stdout
        except Exception:
            containers = "Não foi possível listar containers"
        
        # Listar serviços systemd
        try:
            result = subprocess.run(
                ['systemctl', 'list-units', '--type=service', '--state=running', '--no-pager'],
                capture_output=True,
                text=True,
                timeout=10
            )
            services = result.stdout
        except Exception:
            services = "Não foi possível listar serviços"
        
        prompt = f"""Você é um arquiteto de sistemas especialista em homelab.

Containers Docker ativos:
{containers[:300]}

Serviços systemd rodando:
{services[:500]}

Avalie a arquitetura e sugira melhorias para:
1. Performance
2. Resiliência
3. Manutenibilidade
4. Escalabilidade"""
        
        recommendations = await self.call_llm(prompt, max_tokens=600)
        
        return {
            "containers": containers,
            "services_count": len(services.split('\n')),
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }
    
    async def train_local_agent(self, agent_name: str, task: str, solution: str, metadata: Dict = None) -> Dict[str, Any]:
        """Treina agente local com tarefa resolvida"""
        training_data = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "task": task,
            "solution": solution,
            "metadata": metadata or {}
        }
        
        # Salvar training sample em arquivo JSONL
        training_file = f"/tmp/training_{agent_name}_{datetime.now().strftime('%Y%m%d')}.jsonl"
        try:
            with open(training_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(training_data, ensure_ascii=False) + '\n')
            
            advisor_agents_trained_total.labels(agent_name=agent_name).inc()
            
            return {
                "status": "training_data_saved",
                "file": training_file,
                "message": f"Agente {agent_name} será treinado com esta tarefa"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Erro ao salvar training data: {e}"
            }
    
    def handle_bus_message(self, message):
        """Handler para mensagens do bus"""
        try:
            # Processar apenas mensagens direcionadas ao advisor
            if hasattr(message, 'target') and message.target in ('advisor', 'homelab-advisor', 'all'):
                content = message.content
                source = message.source
                
                print(f"📨 Mensagem recebida de {source}: {content[:100]}")
                
                # Responder via IPC
                if self.database_url:
                    try:
                        req_id = publish_request(
                            source="homelab-advisor",
                            target=source,
                            content=f"Advisor processando: {content[:50]}...",
                            metadata={"original_message_id": getattr(message, 'id', None)}
                        )
                        print(f"📤 Resposta IPC publicada: {req_id}")
                    except Exception as e:
                        print(f"⚠️  Erro ao publicar resposta IPC: {e}")
        except Exception as e:
            print(f"❌ Erro ao processar mensagem do bus: {e}")
    
    async def process_ipc_requests(self):
        """Processa requests IPC pendentes"""
        if not self.database_url:
            return
        
        pending = fetch_pending(target='homelab-advisor', limit=10)
        advisor_ipc_pending_requests.set(len(pending))
        
        for req in pending:
            try:
                content = req['content']
                req_id = req['id']
                source = req['source']
                
                print(f"📨 IPC Request #{req_id} de {source}: {content[:100]}")
                
                # Processar request (exemplo: análise de performance)
                if 'performance' in content.lower():
                    result = await self.analyze_performance()
                    response_text = json.dumps(result, ensure_ascii=False)
                elif 'security' in content.lower() or 'safeguard' in content.lower():
                    result = await self.analyze_security()
                    response_text = json.dumps(result, ensure_ascii=False)
                elif 'architecture' in content.lower() or 'arquitetura' in content.lower():
                    result = await self.review_architecture()
                    response_text = json.dumps(result, ensure_ascii=False)
                else:
                    # Request genérico - consultar LLM
                    response_text = await self.call_llm(content, max_tokens=400)
                
                # Responder
                respond(req_id, responder="homelab-advisor", response_text=response_text)
                print(f"✅ Resposta enviada para request #{req_id}")
                
            except Exception as e:
                print(f"❌ Erro ao processar IPC request: {e}")


# Singleton advisor
advisor = HomelabAdvisor()


@app.on_event("startup")
async def startup_event():
    print("🚀 Homelab Advisor Agent iniciado")
    print(f"   Ollama: {advisor.ollama_host}")
    print(f"   Model: {advisor.ollama_model}")
    print(f"   Bus: {'✅ Conectado' if advisor.bus else '❌ Offline'}")
    print(f"   IPC: {'✅ Disponível' if advisor.database_url else '❌ Offline'}")
    
    # Iniciar worker IPC em background
    if advisor.database_url:
        asyncio.create_task(ipc_worker())


async def ipc_worker():
    """Worker para processar requests IPC periodicamente"""
    while True:
        try:
            await advisor.process_ipc_requests()
        except Exception as e:
            print(f"⚠️  Erro no IPC worker: {e}")
        await asyncio.sleep(5)  # Poll a cada 5s


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "agent": "homelab-advisor",
        "ollama_host": advisor.ollama_host,
        "bus_connected": advisor.bus is not None,
        "ipc_available": advisor.database_url is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/generate")
async def generate(req: GenerateRequest):
    """Endpoint de geração genérica (compatibilidade com versão anterior)"""
    result = await advisor.call_llm(req.prompt, req.max_tokens)
    return {"result": result, "model": advisor.ollama_model}


@app.post("/analyze")
async def analyze(req: AnalysisRequest):
    """Análise especializada do homelab"""
    if req.scope == "performance":
        result = await advisor.analyze_performance(req.context)
    elif req.scope == "security":
        result = await advisor.analyze_security(req.context)
    elif req.scope == "architecture":
        result = await advisor.review_architecture(req.context)
    elif req.scope == "safeguards":
        # Análise combinada
        perf = await advisor.analyze_performance(req.context)
        sec = await advisor.analyze_security(req.context)
        result = {
            "performance": perf,
            "security": sec,
            "timestamp": datetime.now().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Scope inválido: {req.scope}")
    
    return result


@app.post("/train")
async def train(req: TrainingRequest):
    """Treina agente local com tarefa resolvida"""
    result = await advisor.train_local_agent(
        agent_name=req.agent_name,
        task=req.task_description,
        solution=req.solution,
        metadata=req.metadata
    )
    return result


@app.post("/bus/publish")
async def bus_publish(source: str, target: str, content: str, message_type: str = "REQUEST"):
    """Publica mensagem no bus (para testes)"""
    if not advisor.bus:
        raise HTTPException(status_code=503, detail="Bus não disponível")
    
    msg_type = MessageType[message_type.upper()]
    message = advisor.bus.publish(
        message_type=msg_type,
        source=source,
        target=target,
        content=content,
        metadata={"via_api": True}
    )
    
    return {
        "status": "published",
        "message_id": message.id if message else None
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8085))
    uvicorn.run(app, host="0.0.0.0", port=port)
