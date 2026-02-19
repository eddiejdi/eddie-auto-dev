#!/usr/bin/env python3
"""
Eddie Real Workload Service
Gera carga de CPU real e produtiva no homelab usando:
- Inferência LLM via Ollama (múltiplos modelos)
- RAG reindex via Advisor Agent
- Embedding computation via nomic-embed-text
- Code analysis via Agents API

Auto-regulador: monitora CPU e ajusta paralelismo para manter ~70-75%
"""
import asyncio
import aiohttp
import time
import os
import json
import logging
import subprocess
import random

# Sentence transformers para embeddings CPU-intensive
try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("real-workload")

# Config
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
ADVISOR_URL = os.getenv("ADVISOR_URL", "http://127.0.0.1:8085")
AGENTS_API_URL = os.getenv("AGENTS_API_URL", "http://127.0.0.1:8503")
TARGET_CPU = float(os.getenv("TARGET_CPU", "75"))
MIN_CPU = float(os.getenv("MIN_CPU", "65"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10"))

# Modelos para inferência (ordenados por custo computacional)
MODELS = [
    "qwen2.5-coder:7b",     # medio - 7B (llama2:13b fica na RAM mas nao e consultado ativamente)
]

# Prompts produtivos para inferência
PROMPTS = [
    "Analyze the following architecture pattern and suggest improvements for a microservices system with 8 specialized agents communicating via a message bus",
    "Write a comprehensive Python function that implements a self-regulating auto-scaler for Docker containers based on CPU and memory metrics",
    "Explain the best practices for implementing a RAG (Retrieval Augmented Generation) system with ChromaDB and sentence-transformers for a multi-agent platform",
    "Design a monitoring and alerting system using Prometheus metrics and Grafana dashboards for a homelab server running Docker containers",
    "Write a detailed technical analysis of the trade-offs between using PostgreSQL IPC vs Redis pub/sub for inter-agent communication in a distributed system",
    "Create a comprehensive deployment strategy for a Flutter web application with a Node.js backend, including CI/CD pipelines with GitHub Actions",
    "Analyze and propose optimizations for a Telegram bot system that routes messages through an LLM with fallback chains",
    "Design a secret management system that provides secure access to credentials via a FastAPI microservice with audit logging",
    "Write a Python implementation of a distributed task scheduler that routes work between local and remote agents based on precision scores",
    "Explain how to implement end-to-end Selenium testing for a Flutter web application with dynamic content loading",
    "Create a systemd service configuration guide for managing multiple interconnected services with proper dependency ordering",
    "Design a conversation interceptor that captures agent-to-agent messages, detects phases, and persists to PostgreSQL",
]


# Textos longos para batch embedding com sentence-transformers (CPU-intensive)
ST_BATCH_TEXTS = [
    "Docker container orchestration patterns for multi-agent systems with specialized roles including Python JavaScript TypeScript Go Rust Java CSharp and PHP agents communicating via a centralized message bus architecture",
    "Implementing a comprehensive monitoring stack with Prometheus metrics exporters Grafana dashboards and intelligent alerting systems for homelab infrastructure running multiple microservices",
    "Building a secure secrets management microservice with FastAPI that provides encrypted storage access control audit logging and integration with systemd services through environment variable injection",
    "Designing a conversation interceptor system that captures inter-agent communications detects conversation phases from initiation through completion and persists metadata to PostgreSQL for analysis",
    "Flutter web application architecture with provider state management Google Maps integration Firebase authentication real-time geolocation tracking and responsive design for crowd estimation features",
    "Continuous integration and deployment pipeline optimization with GitHub Actions self-hosted runners parallel test execution artifact caching and automated deployment to homelab servers via SSH",
    "Machine learning model serving infrastructure using Ollama for local LLM inference with multiple quantized models automatic model loading and request queuing for optimal resource utilization",
    "Implementing retrieval augmented generation systems with ChromaDB vector storage recursive document indexing from repositories semantic search optimization and multi-category document classification",
    "PostgreSQL database optimization for inter-process communication including connection pooling query performance tuning index strategies for message bus tables and deadlock prevention",
    "Advanced Selenium end-to-end testing strategies for single-page applications including dynamic element waiting shadow DOM traversal screenshot capture and resilient selector strategies",
    "Kubernetes-like container orchestration on a single homelab server using Docker Compose with resource limits health checks automatic restarts and network isolation between service groups",
    "Natural language processing pipeline for multi-language code analysis including abstract syntax tree parsing cyclomatic complexity measurement duplicate detection and automated refactoring suggestions",
]

# Textos para embedding
EMBED_TEXTS = [
    "How to configure Docker networking for inter-container communication",
    "PostgreSQL connection pooling best practices for microservices",
    "Implementing health checks and readiness probes for systemd services",
    "Auto-scaling strategies based on CPU utilization metrics",
    "RAG document indexing and retrieval optimization techniques",
    "Grafana dashboard design patterns for system monitoring",
    "Secure secret management with vault integration",
    "CI/CD pipeline optimization for Flutter and Node.js projects",
]


def get_cpu_percent():
    """Obtém uso atual de CPU via /proc/stat"""
    try:
        result = subprocess.run(
            ["grep", "cpu ", "/proc/stat"],
            capture_output=True, text=True, timeout=5
        )
        parts = result.stdout.strip().split()
        idle = int(parts[4])
        total = sum(int(p) for p in parts[1:])
        time.sleep(0.5)
        result2 = subprocess.run(
            ["grep", "cpu ", "/proc/stat"],
            capture_output=True, text=True, timeout=5
        )
        parts2 = result2.stdout.strip().split()
        idle2 = int(parts2[4])
        total2 = sum(int(p) for p in parts2[1:])
        d_idle = idle2 - idle
        d_total = total2 - total
        if d_total == 0:
            return 50.0
        return round((1 - d_idle / d_total) * 100, 1)
    except Exception as e:
        log.warning(f"Erro ao ler CPU: {e}")
        return 50.0


class WorkloadManager:
    def __init__(self):
        self.active_tasks = 0
        self.max_concurrent = 3
        self.total_completed = 0
        self.total_errors = 0
        self.running = True
        self.session = None
        self._lock = asyncio.Lock()
        self._st_model = None
        self._st_workers = 1  # threads persistentes de ST (llama2:13b já consome muito CPU)

    async def start(self):
        log.info(f"Workload Manager iniciado - Target CPU: {TARGET_CPU}%, Min: {MIN_CPU}%")
        log.info(f"Modelos disponíveis: {len(MODELS)}")
        log.info(f"Prompts disponíveis: {len(PROMPTS)}")

        # Pre-load sentence-transformers model
        if ST_AVAILABLE:
            try:
                self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
                log.info("SentenceTransformer model pre-loaded")
            except Exception as e:
                log.warning(f"Failed to load ST model: {e}")

        timeout = aiohttp.ClientTimeout(total=300)
        self.session = aiohttp.ClientSession(timeout=timeout)

        try:
            tasks = [
                asyncio.create_task(self._cpu_monitor()),
                asyncio.create_task(self._workload_dispatcher()),
                asyncio.create_task(self._stats_reporter()),
            ]
            await asyncio.gather(*tasks)
        finally:
            await self.session.close()

    async def _cpu_monitor(self):
        """Monitora CPU e ajusta paralelismo"""
        while self.running:
            cpu = get_cpu_percent()
            async with self._lock:
                old_max = self.max_concurrent
                if cpu < MIN_CPU:
                    # CPU baixa, aumentar paralelismo
                    self.max_concurrent = min(self.max_concurrent + 1, 8)
                elif cpu > TARGET_CPU:
                    # CPU alta, reduzir paralelismo
                    self.max_concurrent = max(self.max_concurrent - 1, 1)

                if old_max != self.max_concurrent:
                    log.info(f"CPU: {cpu}% | Ajustando paralelismo: {old_max} -> {self.max_concurrent}")
                else:
                    log.debug(f"CPU: {cpu}% | Paralelismo: {self.max_concurrent} | Tasks ativas: {self.active_tasks}")

            await asyncio.sleep(CHECK_INTERVAL)

    async def _workload_dispatcher(self):
        """Despacha tarefas reais mantendo o paralelismo desejado"""
        while self.running:
            async with self._lock:
                slots = self.max_concurrent - self.active_tasks

            if slots > 0:
                for _ in range(slots):
                    task_type = random.choices(
                        ["llm_inference", "embedding", "rag_reindex", "code_analysis", "st_embedding"],
                        weights=[40, 10, 5, 5, 40],
                        k=1
                    )[0]
                    asyncio.create_task(self._run_task(task_type))

            await asyncio.sleep(2)

    async def _run_task(self, task_type: str):
        """Executa uma tarefa real"""
        async with self._lock:
            self.active_tasks += 1

        try:
            if task_type == "llm_inference":
                await self._llm_inference()
            elif task_type == "embedding":
                await self._compute_embeddings()
            elif task_type == "rag_reindex":
                await self._rag_reindex()
            elif task_type == "code_analysis":
                await self._code_analysis()
            elif task_type == "st_embedding":
                await self._st_batch_embedding()

            self.total_completed += 1
        except Exception as e:
            self.total_errors += 1
            log.debug(f"Task {task_type} erro: {e}")
        finally:
            async with self._lock:
                self.active_tasks -= 1

    async def _llm_inference(self):
        """Inferência LLM via Ollama - workload mais pesado"""
        model = random.choice(MODELS)
        prompt = random.choice(PROMPTS)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 256, "temperature": 0.8}
        }
        try:
            async with self.session.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tokens = data.get("eval_count", 0)
                    duration = data.get("total_duration", 0) / 1e9
                    log.info(f"LLM [{model}] {tokens} tokens em {duration:.1f}s")
                else:
                    log.debug(f"LLM [{model}] HTTP {resp.status}")
        except asyncio.TimeoutError:
            log.debug(f"LLM [{model}] timeout")

    async def _compute_embeddings(self):
        """Computa embeddings via nomic-embed-text"""
        text = random.choice(EMBED_TEXTS)
        payload = {
            "model": "nomic-embed-text:latest",
            "prompt": text
        }
        try:
            async with self.session.post(
                f"{OLLAMA_URL}/api/embeddings",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    log.info("Embedding computado com sucesso")
        except Exception:
            pass

    async def _rag_reindex(self):
        """Reindex RAG do Advisor Agent"""
        try:
            async with self.session.post(
                f"{ADVISOR_URL}/rag/reindex",
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    docs = data.get("total_documents", "?")
                    log.info(f"RAG reindex: {docs} docs")
        except Exception:
            pass

    async def _code_analysis(self):
        """Análise de código via Agents API"""
        try:
            async with self.session.get(
                f"{AGENTS_API_URL}/agents/status",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    active = data.get("active_agents", 0)
                    log.info(f"Agents status: {active} ativos")
        except Exception:
            pass


    async def _st_batch_embedding(self):
        """Batch embedding com sentence-transformers - CPU-intensive pesado"""
        if not ST_AVAILABLE or self._st_model is None:
            return
        try:
            loop = asyncio.get_event_loop()
            model = self._st_model  # usa modelo pre-loaded
            def _compute():
                all_texts = ST_BATCH_TEXTS * 5  # 60 textos
                random.shuffle(all_texts)
                total = 0
                for i in range(3):
                    batch = all_texts[i*20:(i+1)*20]
                    embeddings = model.encode(batch, batch_size=8, show_progress_bar=False)
                    total += len(embeddings)
                return total
            count = await loop.run_in_executor(None, _compute)
            log.info(f"ST Embedding: {count} textos processados (heavy)")
        except Exception as e:
            log.debug(f"ST Embedding erro: {e}")


    async def _persistent_st_worker(self):
        """Worker persistente que mantém CPU ocupada com embeddings contínuos"""
        if not ST_AVAILABLE or self._st_model is None:
            log.warning("ST not available, persistent worker disabled")
            return
        
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self._st_workers)
        
        def _continuous_encode(worker_id):
            """Thread que faz encoding contínuo"""
            model = self._st_model
            while self.running:
                cpu = get_cpu_percent()
                if cpu > TARGET_CPU:
                    time.sleep(1)
                    continue
                texts = ST_BATCH_TEXTS * 4  # 48 textos por ciclo
                random.shuffle(texts)
                try:
                    embeddings = model.encode(texts, batch_size=16, show_progress_bar=False)
                    self.total_completed += 1
                except Exception:
                    self.total_errors += 1
                    time.sleep(2)
        
        log.info(f"Iniciando {self._st_workers} ST workers persistentes")
        loop = asyncio.get_event_loop()
        futures = []
        for i in range(self._st_workers):
            fut = loop.run_in_executor(executor, _continuous_encode, i)
            futures.append(fut)
        await asyncio.gather(*futures)

    async def _stats_reporter(self):
        """Reporta estatísticas periodicamente"""
        while self.running:
            await asyncio.sleep(60)
            cpu = get_cpu_percent()
            log.info(
                f"=== STATS === CPU: {cpu}% | "
                f"Paralelismo: {self.max_concurrent} | "
                f"Ativas: {self.active_tasks} | "
                f"Completas: {self.total_completed} | "
                f"Erros: {self.total_errors}"
            )


if __name__ == "__main__":
    manager = WorkloadManager()
    try:
        asyncio.run(manager.start())
    except KeyboardInterrupt:
        log.info("Workload Manager encerrado")
        manager.running = False
