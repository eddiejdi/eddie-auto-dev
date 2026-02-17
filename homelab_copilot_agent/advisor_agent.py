#!/usr/bin/env python3
"""
Homelab Advisor Agent
Consultor especialista para o servidor homelab conectado ao barramento.
Integrado com: IPC (PostgreSQL), Scheduler periódico, API principal (8503).
"""
import os
import sys
import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("homelab-advisor")

try:
    from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
    BUS_AVAILABLE = True
except ImportError:
    BUS_AVAILABLE = False
    logger.warning("Bus in-memory não disponível")

try:
    from tools.agent_ipc import publish_request, poll_response, fetch_pending, respond, init_table
    IPC_AVAILABLE = True
except ImportError:
    IPC_AVAILABLE = False
    logger.warning("IPC module não disponível")


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

# --- Métricas Scheduler ---
advisor_scheduler_runs_total = Counter(
    "advisor_scheduler_runs_total",
    "Total de execuções do scheduler",
    ["scope"]
)

advisor_scheduler_errors_total = Counter(
    "advisor_scheduler_errors_total",
    "Total de erros do scheduler",
    ["scope"]
)

advisor_scheduler_last_run_timestamp = Gauge(
    "advisor_scheduler_last_run_timestamp",
    "Timestamp da última execução do scheduler",
    ["scope"]
)

# --- Métricas API Integration ---
advisor_api_reports_total = Counter(
    "advisor_api_reports_total",
    "Total de relatórios enviados à API principal",
    ["status"]
)

advisor_api_registration_status = Gauge(
    "advisor_api_registration_status",
    "Status de registro na API principal (1=registrado, 0=não)"
)

advisor_ipc_messages_processed_total = Counter(
    "advisor_ipc_messages_processed_total",
    "Total de mensagens IPC processadas",
    ["result"]
)

# --- Heartbeat metric (used to detect agent liveness in logs/alerts)
advisor_heartbeat_timestamp = Gauge(
    "advisor_heartbeat_timestamp",
    "Unix timestamp of last advisor heartbeat"
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
        self.api_base_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:8503")
        
        # Intervalos do scheduler (minutos)
        self.perf_interval = int(os.environ.get("SCHEDULER_PERFORMANCE_INTERVAL", "30"))
        self.sec_interval = int(os.environ.get("SCHEDULER_SECURITY_INTERVAL", "120"))
        self.arch_interval = int(os.environ.get("SCHEDULER_ARCHITECTURE_INTERVAL", "360"))
        
        # Último resultado de cada análise (cache para consultas rápidas)
        self.last_results: Dict[str, Dict] = {}
        
        # Bus in-memory (somente se estiver dentro do mesmo processo)
        self.bus = None
        if BUS_AVAILABLE:
            try:
                self.bus = get_communication_bus()
                self.bus.subscribe(self.handle_bus_message)
                logger.info("✅ Subscribed to communication bus")
            except Exception as e:
                logger.warning(f"Bus init failed: {e}")
        
        # IPC via PostgreSQL
        self.ipc_ready = False
        if IPC_AVAILABLE and self.database_url:
            try:
                init_table()
                self.ipc_ready = True
                logger.info("✅ IPC table initialized (PostgreSQL)")
            except Exception as e:
                logger.warning(f"IPC init failed: {e}")
    
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
            logger.error(f"LLM error ({err_type}): {exc}")
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
        """Handler para mensagens do bus (inclui alerts de 'monitoring').

        - passa a aceitar mensagens cujo `target` seja `monitoring`;
        - quando recebe um alerta (metadata.severity) agenda um handler assíncrono
          que executa uma análise rápida e responde via IPC/operations.
        """
        try:
            targets = ('advisor', 'homelab-advisor', 'monitoring', 'all')
            if hasattr(message, 'target') and message.target in targets:
                content = (message.content or "")
                source = getattr(message, 'source', 'unknown')
                logger.info(f"📨 Bus msg de {source} (target={getattr(message, 'target', '')}): {content[:200]}")

                # detectar severidade (se vier em metadata)
                severity = None
                if hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                    severity = message.metadata.get('severity') or message.metadata.get('level')
                    if severity:
                        severity = str(severity).lower()

                # Se for um alerta crítico/warning, tratar assincronamente
                if severity in ('critical', 'warning'):
                    try:
                        # disparar worker assíncrono para não bloquear o callback do bus
                        asyncio.get_running_loop().create_task(self._handle_alert(message))
                    except RuntimeError:
                        # fallback caso não exista loop corrente
                        asyncio.create_task(self._handle_alert(message))
                    return

                # comportamento padrão: ecoar/ack via IPC para o originador
                if self.ipc_ready:
                    try:
                        req_id = publish_request(
                            source="homelab-advisor",
                            target=source,
                            content=f"Advisor acknowledged: {content[:50]}",
                            metadata={"original_message_id": getattr(message, 'id', None)}
                        )
                        logger.info(f"📤 Resposta IPC publicada: {req_id}")
                    except Exception as e:
                        logger.error(f"Erro ao publicar resposta IPC: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar mensagem do bus: {e}")

    async def _handle_alert(self, message):
        """Trata alertas vindos do bus: executa check rápido e responde ao originador."""
        try:
            md = getattr(message, 'metadata', {}) or {}
            severity = (md.get('severity') or md.get('level') or '').lower()
            alert_name = md.get('alert_name') or md.get('name') or 'grafana_alert'
            instance = md.get('instance') or 'unknown'

            logger.info(f"⚠️ Handling alert {alert_name} severity={severity} instance={instance}")

            # ação para alertas críticos: análise rápida de performance + resposta
            if severity == 'critical':
                result = await self.analyze_performance()
                summary = self._summarize_result('performance', result)
                recommendations = result.get('recommendations', '')

                response_text = (
                    f"Alert handled: {alert_name} ({severity}) on {instance}\n"
                    f"Summary: {summary}\n"
                    f"Recommendations: {recommendations[:1200]}"
                )

                # publicar resposta via IPC para o originador do alerta
                if self.ipc_ready:
                    try:
                        rid = publish_request(
                            source='homelab-advisor',
                            target=getattr(message, 'source', 'monitoring'),
                            content=response_text,
                            metadata={'original_message_id': getattr(message, 'id', None), 'alert_handled': True}
                        )
                        logger.info(f"📨 IPC response for alert published: {rid}")
                    except Exception as e:
                        logger.error(f"Erro ao publicar resposta IPC do alerta: {e}")

                # também publicar um relatório para operations (se disponível)
                if self.ipc_ready:
                    try:
                        publish_request(
                            source='homelab-advisor',
                            target='operations',
                            content=f"Automatic incident report: {alert_name} on {instance}",
                            metadata={'severity': severity, 'summary': summary}
                        )
                    except Exception as e:
                        logger.debug(f"Não foi possível publicar relatório para operations: {e}")

            elif severity == 'warning':
                # para warnings, coletar métricas e enviar resumo curto
                result = await self.analyze_performance()
                summary = self._summarize_result('performance', result)
                response_text = f"Warning observed: {alert_name} on {instance} — {summary}"

                if self.ipc_ready:
                    try:
                        publish_request(source='homelab-advisor', target=getattr(message, 'source', 'monitoring'), content=response_text, metadata={'alert_handled': True})
                    except Exception as e:
                        logger.debug(f"IPC publish (warning) falhou: {e}")

            else:
                # outros tipos: registrar e ignorar (pode ser expandido)
                logger.info(f"Alert received (no-op): {alert_name} severity={severity}")

        except Exception as e:
            logger.error(f"Erro em _handle_alert: {e}")
    
    async def process_ipc_requests(self):
        """Processa requests IPC pendentes"""
        if not self.ipc_ready:
            return
        
        try:
            pending = fetch_pending(target='homelab-advisor', limit=10)
        except Exception as e:
            logger.error(f"Erro ao buscar IPC pendentes: {e}")
            advisor_ipc_pending_requests.set(0)
            return
        
        advisor_ipc_pending_requests.set(len(pending))
        
        for req in pending:
            try:
                content = req['content']
                req_id = req['id']
                source = req['source']
                
                logger.info(f"📨 IPC Request #{req_id} de {source}: {content[:100]}")
                
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
                    response_text = await self.call_llm(content, max_tokens=400)
                
                respond(req_id, responder="homelab-advisor", response_text=response_text)
                advisor_ipc_messages_processed_total.labels(result="success").inc()
                logger.info(f"✅ Resposta enviada para IPC #{req_id}")
                
            except Exception as e:
                advisor_ipc_messages_processed_total.labels(result="error").inc()
                logger.error(f"Erro ao processar IPC request #{req.get('id','?')}: {e}")

    # ==================== Scheduler ====================
    async def scheduled_analysis(self, scope: str):
        """Executa análise agendada e reporta à API principal"""
        logger.info(f"🕐 Scheduler: iniciando análise '{scope}'")
        try:
            if scope == "performance":
                result = await self.analyze_performance()
            elif scope == "security":
                result = await self.analyze_security()
            elif scope == "architecture":
                result = await self.review_architecture()
            else:
                logger.warning(f"Scheduler: scope desconhecido: {scope}")
                return
            
            self.last_results[scope] = result
            advisor_scheduler_runs_total.labels(scope=scope).inc()
            advisor_scheduler_last_run_timestamp.labels(scope=scope).set(time.time())
            
            # Reportar resultado à API principal
            await self.report_to_api(scope, result)
            
            # Publicar no IPC para outros agentes consumirem
            if self.ipc_ready:
                try:
                    publish_request(
                        source="homelab-advisor",
                        target="coordinator",
                        content=f"Análise {scope} completada automaticamente",
                        metadata={
                            "scope": scope,
                            "summary": self._summarize_result(scope, result),
                            "timestamp": datetime.now().isoformat(),
                            "auto_scheduled": True
                        }
                    )
                except Exception as e:
                    logger.warning(f"IPC publish para coordinator falhou: {e}")
            
            logger.info(f"✅ Scheduler: análise '{scope}' completa")
            
        except Exception as e:
            advisor_scheduler_errors_total.labels(scope=scope).inc()
            logger.error(f"❌ Scheduler: erro em análise '{scope}': {e}")
    
    def _summarize_result(self, scope: str, result: Dict) -> str:
        """Gera resumo curto do resultado para IPC"""
        if scope == "performance":
            m = result.get("metrics", {})
            return f"CPU:{m.get('cpu_percent',0)}% MEM:{m.get('memory_percent',0)}% DISK:{m.get('disk_percent',0)}%"
        elif scope == "security":
            r = result.get("recommendations", "")
            return r[:200] if r else "sem recomendações"
        elif scope == "architecture":
            return f"containers analisados, serviços: {result.get('services_count', 0)}"
        return "análise concluída"

    # ==================== API Integration (8503) ====================
    async def register_at_api(self):
        """Registra este agente na API principal (8503)"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Verificar se a API está saudável
                r = await client.get(f"{self.api_base_url}/health")
                if r.status_code != 200:
                    logger.warning(f"API principal não saudável: {r.status_code}")
                    advisor_api_registration_status.set(0)
                    return False
                
                # Publicar via IPC que o advisor está online
                if self.ipc_ready:
                    publish_request(
                        source="homelab-advisor",
                        target="coordinator",
                        content="Homelab Advisor Agent online e operacional",
                        metadata={
                            "agent_type": "homelab-advisor",
                            "capabilities": ["performance", "security", "architecture", "safeguards"],
                            "port": 8085,
                            "scheduler_active": True,
                            "intervals": {
                                "performance_min": self.perf_interval,
                                "security_min": self.sec_interval,
                                "architecture_min": self.arch_interval
                            }
                        }
                    )
                
                advisor_api_registration_status.set(1)
                logger.info("✅ Registrado na API principal via IPC")
                return True
                
        except Exception as e:
            advisor_api_registration_status.set(0)
            logger.warning(f"Registro na API falhou: {e}")
            return False
    
    async def report_to_api(self, scope: str, result: Dict):
        """Reporta resultado de análise à API principal"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "source": "homelab-advisor",
                    "scope": scope,
                    "summary": self._summarize_result(scope, result),
                    "timestamp": datetime.now().isoformat(),
                    "auto_scheduled": True
                }
                
                # Tentar reportar via health/status
                r = await client.get(f"{self.api_base_url}/health")
                if r.status_code == 200:
                    advisor_api_reports_total.labels(status="success").inc()
                    # Armazenar resultado via IPC (persistência real)
                    if self.ipc_ready:
                        publish_request(
                            source="homelab-advisor",
                            target="operations",
                            content=f"Relatório automático: {scope}",
                            metadata={
                                "report_type": scope,
                                "data": self._summarize_result(scope, result),
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                else:
                    advisor_api_reports_total.labels(status="api_unavailable").inc()
                    
        except Exception as e:
            advisor_api_reports_total.labels(status="error").inc()
            logger.warning(f"Report à API falhou: {e}")
    
    async def check_api_tasks(self):
        """Verifica se há tarefas atribuídas a este agente na API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{self.api_base_url}/health")
                if r.status_code == 200:
                    api_data = r.json()
                    logger.debug(f"API health: {api_data.get('status', 'unknown')}")
        except Exception:
            pass  # Silencioso — não bloquear por falha da API


# Singleton advisor
advisor = HomelabAdvisor()


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Homelab Advisor Agent iniciado")
    logger.info(f"   Ollama: {advisor.ollama_host}")
    logger.info(f"   Model: {advisor.ollama_model}")
    logger.info(f"   Bus: {'✅ Conectado' if advisor.bus else '❌ Offline'}")
    logger.info(f"   IPC: {'✅ Disponível' if advisor.ipc_ready else '❌ Offline'}")
    logger.info(f"   API: {advisor.api_base_url}")
    logger.info(f"   Scheduler: perf={advisor.perf_interval}m, sec={advisor.sec_interval}m, arch={advisor.arch_interval}m")
    
    # Iniciar worker IPC em background
    if advisor.ipc_ready:
        asyncio.create_task(ipc_worker())
        logger.info("🔄 IPC worker iniciado (poll a cada 5s)")
    
    # Iniciar scheduler de análises periódicas
    asyncio.create_task(scheduler_worker())
    logger.info("🕐 Scheduler de análises iniciado")

    # Iniciar heartbeat worker (emite log 'advisor_heartbeat' + metric)
    asyncio.create_task(heartbeat_worker())
    # Garantir que o metric exista imediatamente após startup (evita gaps entre startup e 1ª iteração)
    try:
        advisor_heartbeat_timestamp.set(time.time())
        logger.info("💓 Heartbeat metric inicializado no startup")
    except Exception as _:
        logger.exception("Erro ao setar advisor_heartbeat_timestamp no startup")
    logger.info("💓 Heartbeat worker iniciado")
    
    # Registrar na API principal
    asyncio.create_task(api_registration_worker())
    logger.info("🔗 API registration worker iniciado")


async def ipc_worker():
    """Worker para processar requests IPC periodicamente"""
    while True:
        try:
            await advisor.process_ipc_requests()
        except Exception as e:
            logger.error(f"Erro no IPC worker: {e}")
        await asyncio.sleep(5)


async def scheduler_worker():
    """Worker que executa análises periódicas automaticamente"""
    # Aguardar 30s para o sistema estabilizar antes da primeira análise
    await asyncio.sleep(30)
    
    # Rodar primeira análise de performance imediatamente
    await advisor.scheduled_analysis("performance")
    
    # Tracks para próxima execução de cada scope
    next_run = {
        "performance": time.time() + (advisor.perf_interval * 60),
        "security": time.time() + 60,  # Security 1min após start
        "architecture": time.time() + 120,  # Architecture 2min após start
    }
    
    while True:
        try:
            now = time.time()
            
            for scope, next_time in next_run.items():
                if now >= next_time:
                    await advisor.scheduled_analysis(scope)
                    interval = {
                        "performance": advisor.perf_interval,
                        "security": advisor.sec_interval,
                        "architecture": advisor.arch_interval,
                    }[scope]
                    next_run[scope] = now + (interval * 60)
            
        except Exception as e:
            logger.error(f"Erro no scheduler: {e}")
        
        await asyncio.sleep(30)  # Verificar a cada 30s


async def api_registration_worker():
    """Worker que mantém registro na API principal"""
    await asyncio.sleep(10)  # Aguardar startup
    
    while True:
        try:
            await advisor.register_at_api()
            # Re-registrar a cada 10 minutos
            await asyncio.sleep(600)
        except Exception as e:
            logger.error(f"Erro no API registration: {e}")
            await asyncio.sleep(60)  # Retry em 1 min em caso de erro


async def heartbeat_worker():
    """Periodic heartbeat log + metric to verify log ingestion and liveness."""
    while True:
        try:
            # Human-readable log line (picked up by promtail) and metric for alerts
            logger.info("💓 advisor_heartbeat")
            advisor_heartbeat_timestamp.set(time.time())
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        await asyncio.sleep(60)


@app.get("/health")
async def health():
    """Health check com status completo de todas as integrações"""
    return {
        "status": "healthy",
        "agent": "homelab-advisor",
        "ollama_host": advisor.ollama_host,
        "bus_connected": advisor.bus is not None,
        "ipc_available": advisor.ipc_ready,
        "api_base_url": advisor.api_base_url,
        "scheduler": {
            "active": True,
            "intervals": {
                "performance_min": advisor.perf_interval,
                "security_min": advisor.sec_interval,
                "architecture_min": advisor.arch_interval
            },
            "last_results": {
                scope: result.get("timestamp", "nunca")
                for scope, result in advisor.last_results.items()
            }
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/status")
async def status():
    """Retorna último resultado de cada análise do scheduler"""
    return {
        "agent": "homelab-advisor",
        "last_analyses": {
            scope: {
                "timestamp": result.get("timestamp"),
                "summary": advisor._summarize_result(scope, result)
            }
            for scope, result in advisor.last_results.items()
        },
        "ipc_ready": advisor.ipc_ready,
        "scheduler_scopes": ["performance", "security", "architecture"],
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
