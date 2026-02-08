#!/usr/bin/env python3
"""Run the Diretor as a long-running service that listens on the AgentCommunicationBus.

The Diretor is the central authority of the Eddie Auto-Dev system.  It subscribes
to REQUEST messages targeted at 'DIRETOR' (or 'diretor'), processes them using
the Ollama LLM, and publishes a RESPONSE back via the bus.

If DATABASE_URL is set, it also polls the Postgres IPC table for cross-process
requests (from systemd services like coordinator and telegram-bot).

Usage (direct):
    python3 dev_agent/run_diretor_service.py

Usage (via systemd):
    tools/start_diretor.sh   (which calls this script)
"""
import asyncio
import json
import os
import signal
import sys
import time
import traceback
import threading
from datetime import datetime
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
DIRECTOR_MODEL = os.getenv("DIRECTOR_MODEL", "qwen2.5-coder:7b")
DB_IPC_POLL_INTERVAL = int(os.getenv("DIRETOR_DB_POLL", "10"))  # seconds

SYSTEM_PROMPT = """Você é o DIRETOR do sistema Eddie Auto-Dev.

PRIORIDADE PRINCIPAL: a saúde e estabilidade do sistema vêm primeiro. Tome decisões conservadoras.

REGRAS DE CONDUTA (prioritárias):
- Antes de autorizar mudanças que afetem rede, infraestrutura, deploys ou dados, verifique sinais de saúde (logs, /health, status dos serviços). Se houver incerteza, exija intervenção humana explícita.
- Nunca execute ações destrutivas automaticamente. Prefira recomendações em modo 'dry-run' ou passos para um operador humano executar.

RESPONSABILIDADES:
1. Coordenar a equipe de agents especializados com foco em segurança operacional.
2. Aplicar as 10 regras do sistema, interpretando-as de forma conservadora.
3. Garantir o pipeline: Análise → Design → Código → Testes → Deploy — e sempre incluir checagens de saúde antes do Deploy.
4. Economizar tokens (preferir Ollama local) sem comprometer segurança.
5. Validar entregas; quando em dúvida, solicitar revisão humana e evidências (logs, métricas).

Quando solicitarem ações de alto impacto (deploy, reinício de serviços, alteração de DNS, alteração de secrets), responda com um plano passo-a-passo seguro, riscos identificados e peça confirmação humana antes de executar.

Responda de forma clara e objetiva. Se precisar delegar, indique qual agent deve executar.
Se for uma tarefa complexa, quebre em etapas seguindo o pipeline."""


# ---------------------------------------------------------------------------
# Ollama helper
# ---------------------------------------------------------------------------
def query_ollama(prompt: str, model: str = None) -> str:
    """Send a prompt to Ollama and return the response text."""
    import urllib.request
    import urllib.error

    model = model or DIRECTOR_MODEL
    url = f"{OLLAMA_HOST}/api/generate"
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "(sem resposta)")
    except urllib.error.URLError as e:
        return f"[Erro Ollama] {e}"
    except Exception as e:
        return f"[Erro] {e}"


# ---------------------------------------------------------------------------
# Bus message handler
# ---------------------------------------------------------------------------
def handle_message(msg):
    """Process incoming bus messages targeted at the Diretor."""
    try:
        if msg.message_type != MessageType.REQUEST:
            return
        target = (msg.target or "").upper()
        if target not in ("DIRETOR", "DIRECTOR"):
            return

        content = msg.content or ""
        source = msg.source or "unknown"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DiretorService {ts}] REQUEST from {source}: {content[:300]}")

        # Process via Ollama
        response_text = query_ollama(content)
        print(f"[DiretorService {ts}] Response ({len(response_text)} chars): {response_text[:200]}...")

        # Publish response back
        bus = get_communication_bus()
        meta = {"request_id": msg.metadata.get("request_id") if msg.metadata else None}
        bus.publish(MessageType.RESPONSE, "DIRETOR", source, response_text, meta)
        print(f"[DiretorService {ts}] RESPONSE published to {source}")

    except Exception:
        print("[DiretorService] handler error:\n", traceback.format_exc())


# ---------------------------------------------------------------------------
# DB IPC poller (Postgres cross-process requests)
# ---------------------------------------------------------------------------
def _load_agent_ipc():
    """Try to import agent_ipc for Postgres-based IPC."""
    try:
        ipc_path = ROOT / "tools" / "agent_ipc.py"
        if not ipc_path.exists():
            return None
        import importlib.util
        spec = importlib.util.spec_from_file_location("agent_ipc_local", str(ipc_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"[DiretorService] agent_ipc not available: {e}")
        return None


def db_ipc_poll_loop():
    """Poll Postgres IPC table for pending DIRETOR requests and respond."""
    agent_ipc = _load_agent_ipc()
    if agent_ipc is None:
        print("[DiretorService] DB IPC disabled (agent_ipc unavailable)")
        return

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[DiretorService] DB IPC disabled (DATABASE_URL not set)")
        return

    print(f"[DiretorService] DB IPC poller started (interval={DB_IPC_POLL_INTERVAL}s)")
    while True:
        try:
            rows = agent_ipc.fetch_pending("DIRETOR", limit=5)
            for r in rows:
                rid = r["id"]
                src = r.get("source", "unknown")
                content = r.get("content", "")
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[DiretorService-DB {ts}] Processing DB request {rid} from {src}: {str(content)[:200]}")

                response_text = query_ollama(str(content))
                agent_ipc.respond(rid, "DIRETOR", response_text)
                print(f"[DiretorService-DB {ts}] Responded to DB request {rid}")
        except Exception:
            print("[DiretorService-DB] poll error:\n", traceback.format_exc())

        time.sleep(DB_IPC_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print(f"  Diretor Service starting")
    print(f"  Ollama: {OLLAMA_HOST}  Model: {DIRECTOR_MODEL}")
    print(f"  DB IPC poll: {DB_IPC_POLL_INTERVAL}s")
    print(f"  PID: {os.getpid()}")
    print("=" * 60)

    # Subscribe to the bus for in-process messages
    bus = get_communication_bus()
    bus.subscribe(handle_message)
    print("[DiretorService] Subscribed to AgentCommunicationBus, listening for DIRETOR requests...")

    # Start DB IPC poller in a daemon thread
    db_thread = threading.Thread(target=db_ipc_poll_loop, daemon=True, name="diretor-db-ipc")
    db_thread.start()

    # Graceful shutdown
    def _shutdown(signum, frame):
        print(f"\n[DiretorService] Received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Publish a startup announcement
    try:
        bus.publish(
            MessageType.RESPONSE,
            "DIRETOR",
            "all",
            "Diretor Service iniciado e ouvindo requisições.",
            {"event": "startup", "pid": os.getpid()},
        )
    except Exception:
        pass

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("[DiretorService] Shutting down")


if __name__ == "__main__":
    main()
