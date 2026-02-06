#!/usr/bin/env python3
"""
RPA4ALL Code Runner Session Manager
────────────────────────────────────
Per-user Docker containers with session isolation.

Features:
  • Each user session gets its own isolated Docker container
  • Maximum 5 concurrent sessions (configurable)
  • FIFO queue for overflow with position feedback
  • Auto-destroy after 5 minutes of inactivity
  • Graceful shutdown cleans up all containers
  • Stale container cleanup on startup

Usage:
    uvicorn site.code_runner_manager:app --host 0.0.0.0 --port 2000

Env vars:
    MAX_SESSIONS          – max concurrent containers (default 5)
    IDLE_TIMEOUT          – seconds before idle container is destroyed (default 300)
    QUEUE_WAIT_TIMEOUT    – max seconds a queued request blocks (default 30)
    CONTAINER_IMAGE       – Docker image to use (default rpa4all/code-runner)
    PROJECT_MOUNT         – host path mounted as /project in containers
"""

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import docker
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─── Configuration ───────────────────────────────────────────────────────────
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "5"))
IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "300"))  # 5 min
QUEUE_WAIT_TIMEOUT = int(os.getenv("QUEUE_WAIT_TIMEOUT", "30"))
CLEANUP_INTERVAL = 15  # seconds between idle checks
CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE", "rpa4all/code-runner")
CONTAINER_PREFIX = "cr-sess-"
PROJECT_MOUNT = os.getenv("PROJECT_MOUNT", "/home/homelab/eddie-auto-dev")
PATCHED_APP_PATH = os.path.join(PROJECT_MOUNT, "site", "app_patched.py")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("session-mgr")


# ─── Data Classes ────────────────────────────────────────────────────────────
@dataclass
class SessionInfo:
    session_id: str
    container_id: str
    container_ip: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)


@dataclass
class QueueEntry:
    session_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    enqueued_at: float = field(default_factory=time.time)


# ─── Container Pool ─────────────────────────────────────────────────────────
class ContainerPool:
    """Manages a pool of per-session Docker containers."""

    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.queue: List[QueueEntry] = []
        self.lock = asyncio.Lock()
        self.docker: docker.DockerClient = docker.from_env()

    # ── Properties ──────────────────────────────────────────────────────
    @property
    def active_count(self) -> int:
        return len(self.sessions)

    @property
    def queue_size(self) -> int:
        return len(self.queue)

    def has_capacity(self) -> bool:
        return self.active_count < MAX_SESSIONS

    # ── Public API ──────────────────────────────────────────────────────
    async def acquire(self, session_id: str) -> Optional[SessionInfo]:
        """Return an existing or new session. Returns None if at capacity."""
        async with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].last_activity = time.time()
                return self.sessions[session_id]
            if self.has_capacity():
                return await self._create(session_id)
            return None

    async def enqueue_and_wait(self, session_id: str) -> Optional[SessionInfo]:
        """Add to queue and block until a slot opens (or timeout)."""
        entry = QueueEntry(session_id=session_id)
        self.queue.append(entry)
        pos = len(self.queue)
        log.info("Session %s queued at position %d", session_id, pos)

        try:
            await asyncio.wait_for(entry.event.wait(), timeout=QUEUE_WAIT_TIMEOUT)
            async with self.lock:
                if self.has_capacity():
                    return await self._create(session_id)
            return None
        except asyncio.TimeoutError:
            return None
        finally:
            if entry in self.queue:
                self.queue.remove(entry)

    def queue_position(self, session_id: str) -> int:
        for i, e in enumerate(self.queue):
            if e.session_id == session_id:
                return i + 1
        return 0

    async def destroy(self, session_id: str):
        """Stop & remove a session's container, then signal next waiter."""
        async with self.lock:
            info = self.sessions.pop(session_id, None)
        if not info:
            return

        name = f"{CONTAINER_PREFIX}{session_id[:12]}"
        log.info("Destroying container %s", name)
        try:
            c = self.docker.containers.get(info.container_id)
            c.stop(timeout=5)
            c.remove(force=True)
        except Exception as exc:
            log.warning("Error destroying %s: %s", name, exc)

        # wake up next waiter
        if self.queue:
            self.queue[0].event.set()

    async def reap_idle(self):
        """Destroy sessions that exceeded IDLE_TIMEOUT."""
        now = time.time()
        idle = [
            sid
            for sid, info in list(self.sessions.items())
            if (now - info.last_activity) > IDLE_TIMEOUT
        ]
        for sid in idle:
            log.info("Session %s idle >%ds – reaping", sid, IDLE_TIMEOUT)
            await self.destroy(sid)

    async def shutdown(self):
        """Destroy every managed container (graceful shutdown)."""
        for sid in list(self.sessions):
            await self.destroy(sid)

    def purge_stale(self):
        """Remove leftover session containers from previous runs."""
        try:
            for c in self.docker.containers.list(all=True):
                if c.name.startswith(CONTAINER_PREFIX):
                    log.info("Purging stale container %s", c.name)
                    try:
                        c.stop(timeout=3)
                    except Exception:
                        pass
                    c.remove(force=True)
        except Exception as exc:
            log.warning("Error purging stale containers: %s", exc)

    # ── Internal ────────────────────────────────────────────────────────
    async def _create(self, session_id: str) -> SessionInfo:
        name = f"{CONTAINER_PREFIX}{session_id[:12]}"
        log.info("Creating container %s", name)

        volumes = {PROJECT_MOUNT: {"bind": "/project", "mode": "ro"}}
        # Mount patched app.py if available
        if os.path.isfile(PATCHED_APP_PATH):
            volumes[PATCHED_APP_PATH] = {"bind": "/app/app.py", "mode": "ro"}

        container = self.docker.containers.run(
            CONTAINER_IMAGE,
            name=name,
            detach=True,
            environment={
                "MAX_MEMORY_MB": "256",
                "MAX_OUTPUT_SIZE": "65536",
                "MAX_EXECUTION_TIME": "30",
            },
            volumes=volumes,
            mem_limit="512m",
            cpu_period=100000,
            cpu_quota=50000,  # 50 % of one core
            network_mode="bridge",
            auto_remove=False,
        )

        # Wait for container networking + Flask readiness
        container.reload()
        ip = container.attrs["NetworkSettings"]["IPAddress"]

        ready = False
        for attempt in range(15):
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    r = await client.get(f"http://{ip}:5000/health")
                    if r.status_code == 200:
                        ready = True
                        break
            except Exception:
                await asyncio.sleep(0.5)

        if not ready:
            log.error("Container %s never became healthy – removing", name)
            container.stop(timeout=3)
            container.remove(force=True)
            raise RuntimeError(f"Container {name} failed health check")

        info = SessionInfo(
            session_id=session_id,
            container_id=container.id,
            container_ip=ip,
        )
        self.sessions[session_id] = info
        log.info("Container %s ready @ %s", name, ip)
        return info


# ─── FastAPI Application ────────────────────────────────────────────────────
pool = ContainerPool()
_cleanup_task: Optional[asyncio.Task] = None


async def _periodic_cleanup():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            await pool.reap_idle()
        except Exception as exc:
            log.error("Cleanup error: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _cleanup_task
    pool.purge_stale()
    _cleanup_task = asyncio.create_task(_periodic_cleanup())
    log.info(
        "Session Manager started – max_sessions=%d idle_timeout=%ds",
        MAX_SESSIONS,
        IDLE_TIMEOUT,
    )
    yield
    _cleanup_task.cancel()
    await pool.shutdown()
    log.info("Session Manager stopped – all containers destroyed")


app = FastAPI(title="RPA4ALL Code Runner Manager", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rpa4all.com",
        "https://www.rpa4all.com",
        "http://localhost:8081",
        "http://localhost:8080",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-ID"],
)


# ─── Routes ─────────────────────────────────────────────────────────────────
@app.post("/api/v2/execute")
async def execute(request: Request):
    """Execute Python code in a per-session container."""
    session_id = request.headers.get("X-Session-ID") or uuid.uuid4().hex[:12]

    # Parse body
    data = await request.json()
    files = data.get("files", [])
    if not files:
        return JSONResponse(
            status_code=400,
            content={"run": {"stdout": "", "stderr": "Nenhum código fornecido", "code": 1}},
        )
    code = files[0].get("content", "")
    stdin_text = data.get("stdin", "")
    language = data.get("language", "python")
    if language not in ("python", "python3", "py"):
        return JSONResponse(
            status_code=400,
            content={
                "run": {"stdout": "", "stderr": f"Linguagem '{language}' não suportada", "code": 1}
            },
        )

    # Acquire session
    session = await pool.acquire(session_id)

    if session is None:
        # At capacity – try waiting in queue
        session = await pool.enqueue_and_wait(session_id)

    if session is None:
        # Still no slot
        return JSONResponse(
            status_code=202,
            content={
                "queued": True,
                "position": pool.queue_position(session_id) or pool.queue_size + 1,
                "session_id": session_id,
                "active_sessions": pool.active_count,
                "max_sessions": MAX_SESSIONS,
                "retry_after": 5,
                "message": f"⏳ Servidor ocupado – {pool.active_count}/{MAX_SESSIONS} sessões ativas. Posição na fila: {pool.queue_size + 1}. Tentando novamente em 5 s…",
            },
        )

    # Proxy to container
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.post(
                f"http://{session.container_ip}:5000/api/v2/execute",
                json={
                    "language": language,
                    "files": [{"content": code}],
                    "stdin": stdin_text,
                },
            )
            result = resp.json()
            result["session_id"] = session_id
            return JSONResponse(
                content=result,
                headers={"X-Session-ID": session_id},
            )
    except Exception as exc:
        log.error("Proxy error for session %s: %s", session_id, exc)
        # Container may have died – destroy session so next request creates fresh one
        await pool.destroy(session_id)
        return JSONResponse(
            status_code=500,
            content={
                "run": {"stdout": "", "stderr": f"Erro na execução: {exc}", "code": 1},
                "session_id": session_id,
            },
        )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "rpa4all-code-runner-manager",
        "version": "2.0.0",
        "active_sessions": pool.active_count,
        "max_sessions": MAX_SESSIONS,
        "queue_size": pool.queue_size,
        "idle_timeout": IDLE_TIMEOUT,
    }


@app.get("/sessions")
async def list_sessions():
    now = time.time()
    return {
        "capacity": f"{pool.active_count}/{MAX_SESSIONS}",
        "active": [
            {
                "session_id": s.session_id,
                "container_ip": s.container_ip,
                "created_at": int(s.created_at),
                "idle_seconds": int(now - s.last_activity),
            }
            for s in pool.sessions.values()
        ],
        "queue": [
            {
                "session_id": e.session_id,
                "waiting_seconds": int(now - e.enqueued_at),
            }
            for e in pool.queue
        ],
    }


@app.delete("/sessions/{session_id}")
async def force_destroy(session_id: str):
    if session_id not in pool.sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    await pool.destroy(session_id)
    return {"message": f"Session {session_id} destroyed", "active": pool.active_count}


@app.get("/api/v2/runtimes")
async def runtimes():
    return [{"language": "python", "version": "3.11", "aliases": ["py", "python3"]}]


@app.get("/api/v2/packages")
async def packages():
    return {
        "language": "python",
        "packages": [
            "numpy", "pandas", "matplotlib", "requests", "httpx",
            "pydantic", "chromadb", "paramiko", "aiohttp", "psutil",
        ],
    }


@app.get("/")
async def root():
    return {
        "service": "RPA4ALL Code Runner Manager",
        "version": "2.0.0",
        "features": [
            "per-session Docker isolation",
            "max 5 concurrent sessions",
            "FIFO queue with position feedback",
            "auto-destroy after inactivity",
        ],
        "active_sessions": pool.active_count,
        "max_sessions": MAX_SESSIONS,
    }
