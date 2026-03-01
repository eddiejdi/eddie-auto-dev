#!/usr/bin/env python3
"""Prometheus exporter + self-healing for trading agents (BTC, ETH, XRP, SOL, DOGE, ADA).

Usage:
  python3 trading_selfheal_exporter.py --port 9120

Metrics exposed (Prometheus format):
  trading_agent_up{symbol}                         — 1 if healthy, 0 if down
  trading_agent_stalled{symbol}                    — 1 if stalled (no decisions), 0 if ok
  trading_agent_last_decision_age_seconds{symbol}  — age of last decision
  trading_agent_restart_total{symbol}              — auto-restart counter
  trading_agent_consecutive_failures{symbol}       — consecutive health check failures
  trading_selfheal_actions_total{action,symbol}    — total actions (restart, recovered, rate_limited, ollama_error)
  trading_ollama_analyze_total{symbol}             — Ollama analyses conducted before restart
  trading_ollama_analysis_latency_seconds{symbol}  — Ollama analysis time

Systemd service: trading-selfheal-exporter.service
Self-healing: restarts trading agents when stalled; uses Ollama to diagnose errors before restart
Ollama integration: analyzes agent logs via LLM to detect root cause of stalls (deadlock, API timeout, DB lock, etc.)
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
import threading
import httpx
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    from prometheus_client import start_http_server, Counter, Gauge, Summary
    HAS_PROM = True
except ImportError:
    HAS_PROM = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [trading-heal] %(message)s",
)
log = logging.getLogger("trading-heal")

# ── Configuration ──────────────────────────────────────────────────────

DATA_DIR = os.environ.get("TRADING_HEAL_DATA_DIR", "/var/lib/eddie/trading-heal")
AUDIT_LOG = os.path.join(DATA_DIR, "trading_heal_audit.jsonl")
MAX_RESTARTS_PER_HOUR = int(os.environ.get("TRADING_HEAL_MAX_RESTARTS", "3"))
CHECK_INTERVAL = int(os.environ.get("TRADING_HEAL_INTERVAL", "30"))  # seconds
COOLDOWN_AFTER_RESTART = int(os.environ.get("TRADING_HEAL_COOLDOWN", "60"))  # seconds
STALL_THRESHOLD = int(os.environ.get("TRADING_HEAL_STALL_THRESHOLD", "600"))  # 10 min

# PostgreSQL
DB_HOST = os.environ.get("POSTGRES_HOST", "192.168.15.2")
DB_PORT = int(os.environ.get("POSTGRES_PORT", "5433"))
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "eddie_memory_2026")
DB_NAME = os.environ.get("POSTGRES_DB", "postgres")

# Ollama integration
OLLAMA_ENABLED = os.environ.get("OLLAMA_ENABLED", "true").lower() == "true"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "30"))

# ── Trading agent definitions ──────────────────────────────────────────


@dataclass
class TradingAgentDef:
    """Definition of a trading agent to monitor."""
    symbol: str  # e.g., "BTC-USDT"
    systemd_unit: str  # e.g., "crypto-agent@BTC_USDT.service"
    exporter_port: int  # 9092-9097
    pg_schema: str = "btc"  # PostgreSQL schema
    enabled: bool = True


DEFAULT_AGENTS: List[TradingAgentDef] = [
    TradingAgentDef(symbol="BTC-USDT", systemd_unit="crypto-agent@BTC_USDT.service", exporter_port=9092),
    TradingAgentDef(symbol="ETH-USDT", systemd_unit="crypto-agent@ETH_USDT.service", exporter_port=9093),
    TradingAgentDef(symbol="XRP-USDT", systemd_unit="crypto-agent@XRP_USDT.service", exporter_port=9094),
    TradingAgentDef(symbol="SOL-USDT", systemd_unit="crypto-agent@SOL_USDT.service", exporter_port=9095),
    TradingAgentDef(symbol="DOGE-USDT", systemd_unit="crypto-agent@DOGE_USDT.service", exporter_port=9096),
    TradingAgentDef(symbol="ADA-USDT", systemd_unit="crypto-agent@ADA_USDT.service", exporter_port=9097),
]


# ── Agent health state ─────────────────────────────────────────────────


@dataclass
class AgentState:
    up: bool = False
    stalled: bool = False
    last_check: float = 0
    last_decision_timestamp: float = 0
    consecutive_failures: int = 0
    restarts_this_hour: int = 0
    restarts_total: int = 0
    last_restart: float = 0
    hour_window_start: float = 0
    ollama_analyses_total: int = 0
    last_ollama_latency: float = 0


# ── Health check engine ────────────────────────────────────────────────


class TradingAgentHealthChecker:
    """Checks agent health and performs self-healing restarts with Ollama diagnostics."""

    def __init__(self, agents: List[TradingAgentDef]):
        self.agents = {a.symbol: a for a in agents}
        self.states: Dict[str, AgentState] = {a.symbol: AgentState() for a in agents}
        self._lock = threading.Lock()
        self.db_conn = None
        self._init_db()

    def _init_db(self):
        """Initialize PostgreSQL connection."""
        if not HAS_PSYCOPG2:
            log.warning("psycopg2 not installed — stall detection disabled")
            return
        try:
            self.db_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME,
            )
            self.db_conn.autocommit = True
            log.info("PostgreSQL connected: %s:%d", DB_HOST, DB_PORT)
        except Exception as e:
            log.error("PostgreSQL connection failed: %s", e)
            self.db_conn = None

    def check_systemd_active(self, unit: str) -> bool:
        """Check if a systemd unit is active."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    def check_process(self, pattern: str) -> bool:
        """Check if a process matching pattern is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_last_decision_timestamp(self, symbol: str) -> Optional[float]:
        """Query PostgreSQL for last decision timestamp (epoch)."""
        if not self.db_conn:
            return None
        try:
            cur = self.db_conn.cursor()
            agent = self.agents.get(symbol)
            if not agent:
                return None
            cur.execute(
                f"SELECT MAX(timestamp) FROM {agent.pg_schema}.decisions WHERE symbol = %s",
                (symbol,),
            )
            result = cur.fetchone()
            return result[0] if result and result[0] else None
        except Exception as e:
            log.warning("DB query error for %s: %s", symbol, e)
            return None

    def get_agent_logs(self, symbol: str, lines: int = 50) -> str:
        """Get recent systemd journal logs for an agent."""
        try:
            agent = self.agents.get(symbol)
            if not agent:
                return ""
            result = subprocess.run(
                ["journalctl", "-u", agent.systemd_unit, "-n", str(lines), "--no-pager"],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout
        except Exception:
            return ""

    async def analyze_with_ollama(self, symbol: str, logs: str, state: AgentState) -> Optional[str]:
        """Use Ollama to analyze logs and detect root cause of stall."""
        if not OLLAMA_ENABLED:
            return None

        start = time.monotonic()
        try:
            prompt = f"""Analyze these trading agent logs for {symbol} and identify the root cause of the stall.
Agent state: last_decision_age={int(time.time() - state.last_decision_timestamp)}s, consecutive_failures={state.consecutive_failures}

Logs (last 50 lines):
{logs[-2000:]}  # Last 2000 chars to save tokens

Provide:
1. Root cause (e.g., "DB lock", "API timeout", "deadlock in market_state", "exception in trade execution")
2. Severity (critical/high/medium/low)
3. Recommended action (auto-restart / manual intervention / wait for retry)
4. Brief explanation (max 100 chars)

Return as JSON: {{"cause": "...", "severity": "...", "action": "...", "explanation": "..."}}"""

            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                response = await client.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": "10m",
                    },
                )
                result = response.json()
                analysis_text = result.get("response", "").strip()
                
                # Try to extract JSON from response
                try:
                    # Find JSON block in response
                    import re
                    match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                    if match:
                        return match.group(0)
                except Exception:
                    pass
                
                return analysis_text if analysis_text else None

        except Exception as e:
            log.warning("Ollama analysis error for %s: %s", symbol, e)
            self._audit("ollama_error", symbol, False, str(e))
            return None
        finally:
            elapsed = time.monotonic() - start
            state.last_ollama_latency = elapsed
            state.ollama_analyses_total += 1

    def restart_service(self, symbol: str, state: AgentState, reason: str = "") -> bool:
        """Restart a trading agent with rate limiting."""
        agent = self.agents.get(symbol)
        if not agent:
            return False

        now = time.time()

        # Reset hourly counter if window expired
        if now - state.hour_window_start > 3600:
            state.restarts_this_hour = 0
            state.hour_window_start = now

        # Rate limit
        if state.restarts_this_hour >= MAX_RESTARTS_PER_HOUR:
            log.warning(
                "RATE LIMIT: %s already restarted %d times this hour — skipping",
                symbol, state.restarts_this_hour,
            )
            self._audit("rate_limited", symbol, False, f"Exceeded {MAX_RESTARTS_PER_HOUR} restarts/hour")
            return False

        # Cooldown
        if now - state.last_restart < COOLDOWN_AFTER_RESTART:
            log.info("COOLDOWN: %s restarted recently — waiting", symbol)
            return False

        log.warning("SELF-HEAL: restarting %s (%s) — reason: %s", symbol, agent.systemd_unit, reason)
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", agent.systemd_unit],
                capture_output=True, text=True, timeout=30,
            )
            success = result.returncode == 0
            state.last_restart = now
            state.restarts_this_hour += 1
            state.restarts_total += 1
            
            detail = f"{reason} | {result.stderr.strip()}" if result.stderr else reason
            self._audit("restart", symbol, success, detail)
            
            if success:
                log.info("SELF-HEAL: %s restarted successfully", symbol)
            else:
                log.error("SELF-HEAL: %s restart FAILED: %s", symbol, result.stderr)
            return success
        except Exception as e:
            log.error("SELF-HEAL: %s restart EXCEPTION: %s", symbol, e)
            self._audit("restart", symbol, False, str(e))
            return False

    def check_agent(self, symbol: str) -> bool:
        """Run all health checks for an agent. Returns True if healthy."""
        agent = self.agents.get(symbol)
        state = self.states[symbol]

        if not agent.enabled:
            state.up = False
            state.last_check = time.time()
            return False

        checks = []

        # 1. Systemd unit active
        systemd_ok = self.check_systemd_active(agent.systemd_unit)
        checks.append(("systemd", systemd_ok))

        # 2. Process running
        pattern = f"trading_agent.py.*{agent.systemd_unit.split('@')[1].split('.')[0]}"
        proc_ok = self.check_process(pattern)
        checks.append(("process", proc_ok))

        # 3. Stall detection via DB (CRITICAL)
        now = time.time()
        last_decision = self.get_last_decision_timestamp(symbol)
        state.last_decision_timestamp = last_decision or 0
        
        if last_decision:
            decision_age = now - last_decision
            stalled = decision_age > STALL_THRESHOLD
            checks.append(("stall", not stalled))
        else:
            # No decisions in DB = stalled
            checks.append(("stall", False))
            stalled = True

        state.stalled = stalled
        state.last_check = now

        # Determine overall health — all checks must pass
        all_ok = all(ok for _, ok in checks) and len(checks) >= 2
        
        if all_ok:
            if state.consecutive_failures > 0:
                log.info("RECOVERED: %s is healthy again after %d failures",
                         symbol, state.consecutive_failures)
                self._audit("recovered", symbol, True,
                            f"after {state.consecutive_failures} failures")
            state.consecutive_failures = 0
            state.up = True
        else:
            state.consecutive_failures += 1
            state.up = False
            failed = [c for c, ok in checks if not ok]
            log.warning("UNHEALTHY: %s — failed checks: %s (attempt %d)",
                        symbol, failed, state.consecutive_failures)

            # Self-heal after 2 consecutive failures
            if state.consecutive_failures >= 2:
                # Get logs for Ollama analysis
                logs = self.get_agent_logs(symbol, lines=50)
                
                # Ollama diagnosis (non-blocking, run in executor)
                ollama_insight = ""
                if OLLAMA_ENABLED and logs:
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        analysis = loop.run_until_complete(
                            self.analyze_with_ollama(symbol, logs, state)
                        )
                        if analysis:
                            ollama_insight = analysis
                            log.info("Ollama analysis for %s: %s", symbol, ollama_insight[:200])
                        loop.close()
                    except Exception as e:
                        log.warning("Ollama analysis failed for %s: %s", symbol, e)
                
                # Restart with reason
                reason = f"stalled (age={int(now - state.last_decision_timestamp)}s)"
                if ollama_insight:
                    reason += f" | Ollama: {ollama_insight[:100]}"
                
                self.restart_service(symbol, state, reason=reason)

        return all_ok

    def check_all(self):
        """Run checks on all agents."""
        for symbol in self.agents:
            try:
                self.check_agent(symbol)
            except Exception as e:
                log.error("CHECK ERROR for %s: %s", symbol, e)

    def _audit(self, action: str, symbol: str, success: bool, detail: str = ""):
        """Append to audit log."""
        try:
            os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "symbol": symbol,
                "success": success,
                "detail": detail,
            }
            with open(AUDIT_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def get_summary(self) -> Dict:
        """Return current state summary."""
        result = {}
        for symbol, state in self.states.items():
            agent = self.agents[symbol]
            now = time.time()
            last_decision_age = now - state.last_decision_timestamp if state.last_decision_timestamp else 9999
            
            result[symbol] = {
                "enabled": agent.enabled,
                "up": state.up,
                "stalled": state.stalled,
                "consecutive_failures": state.consecutive_failures,
                "restarts_total": state.restarts_total,
                "restarts_this_hour": state.restarts_this_hour,
                "last_decision_age_seconds": int(last_decision_age),
                "ollama_analyses_total": state.ollama_analyses_total,
                "last_ollama_latency_seconds": round(state.last_ollama_latency, 2),
                "last_check": datetime.fromtimestamp(
                    state.last_check, tz=timezone.utc
                ).isoformat() if state.last_check else None,
            }
        return result


# ── Prometheus metrics ─────────────────────────────────────────────────


def setup_prometheus_metrics():
    """Create Prometheus metric objects."""
    if not HAS_PROM:
        return None

    metrics = {
        "up": Gauge(
            "trading_agent_up", "Trading agent health status (1=up, 0=down)",
            ["symbol"],
        ),
        "stalled": Gauge(
            "trading_agent_stalled", "Trading agent stalled (1=stalled, 0=ok)",
            ["symbol"],
        ),
        "last_decision_age": Gauge(
            "trading_agent_last_decision_age_seconds", "Age of last decision in seconds",
            ["symbol"],
        ),
        "restart_total": Counter(
            "trading_agent_restart_total", "Total self-heal restarts",
            ["symbol"],
        ),
        "consecutive_failures": Gauge(
            "trading_agent_consecutive_failures", "Consecutive health check failures",
            ["symbol"],
        ),
        "selfheal_actions": Counter(
            "trading_selfheal_actions_total", "Total self-healing actions",
            ["action", "symbol"],
        ),
        "ollama_analyses": Counter(
            "trading_ollama_analyze_total", "Ollama analyses conducted",
            ["symbol"],
        ),
        "ollama_latency": Gauge(
            "trading_ollama_analysis_latency_seconds", "Ollama analysis latency",
            ["symbol"],
        ),
    }
    return metrics


def update_prometheus(checker: TradingAgentHealthChecker, prom_metrics: dict):
    """Push current state to Prometheus gauges/counters."""
    if not prom_metrics:
        return
    
    for symbol, state in checker.states.items():
        now = time.time()
        last_decision_age = now - state.last_decision_timestamp if state.last_decision_timestamp else 9999
        
        prom_metrics["up"].labels(symbol=symbol).set(1 if state.up else 0)
        prom_metrics["stalled"].labels(symbol=symbol).set(1 if state.stalled else 0)
        prom_metrics["last_decision_age"].labels(symbol=symbol).set(int(last_decision_age))
        prom_metrics["consecutive_failures"].labels(symbol=symbol).set(state.consecutive_failures)
        prom_metrics["ollama_latency"].labels(symbol=symbol).set(state.last_ollama_latency)


# ── HTTP status endpoint ───────────────────────────────────────────────


class StatusHandler(BaseHTTPRequestHandler):
    checker: TradingAgentHealthChecker = None

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            summary = self.checker.get_summary() if self.checker else {}
            self.wfile.write(json.dumps(summary, indent=2).encode())
        elif self.path == "/audit" or self.path.startswith("/audit?"):
            self._serve_audit()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_audit(self):
        try:
            lines = []
            if os.path.isfile(AUDIT_LOG):
                with open(AUDIT_LOG) as f:
                    lines = f.readlines()[-50:]  # last 50 entries
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            entries = [json.loads(l) for l in lines if l.strip()]
            self.wfile.write(json.dumps(entries, indent=2).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def log_message(self, format, *args):
        pass  # silence access logs


# ── Main loop ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Trading agent self-healing exporter with Ollama diagnostics")
    parser.add_argument("--port", type=int, default=9120, help="Prometheus metrics port")
    parser.add_argument("--status-port", type=int, default=9121, help="HTTP status/audit port")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL, help="Check interval (s)")
    parser.add_argument("--dry-run", action="store_true", help="Check but don't restart")
    args = parser.parse_args()

    agents = DEFAULT_AGENTS
    checker = TradingAgentHealthChecker(agents)

    # Prometheus
    prom_metrics = None
    if HAS_PROM:
        prom_metrics = setup_prometheus_metrics()
        start_http_server(args.port)
        log.info("Prometheus metrics on :%d", args.port)
    else:
        log.warning("prometheus_client not installed — metrics disabled (pip install prometheus_client)")

    # Status HTTP server
    StatusHandler.checker = checker
    status_server = HTTPServer(("0.0.0.0", args.status_port), StatusHandler)
    status_thread = threading.Thread(target=status_server.serve_forever, daemon=True)
    status_thread.start()
    log.info("Status/audit API on :%d (/health, /status, /audit)", args.status_port)

    # Signal handling
    running = True

    def shutdown(sig, frame):
        nonlocal running
        log.info("Shutting down (signal %s)...", sig)
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("Starting trading agent health-check loop (interval=%ds, dry_run=%s, ollama=%s)",
             args.interval, args.dry_run, OLLAMA_ENABLED)
    log.info("Monitoring %d agents: %s",
             len(agents), [a.symbol for a in agents if a.enabled])

    if args.dry_run:
        # Patch restart to no-op
        original_restart = checker.restart_service
        def noop_restart(symbol, state, reason=""):
            log.info("DRY-RUN: would restart %s (reason: %s)", symbol, reason)
            return False
        checker.restart_service = noop_restart

    while running:
        try:
            checker.check_all()
            if prom_metrics:
                update_prometheus(checker, prom_metrics)

            # Log summary periodically
            summary = checker.get_summary()
            statuses = {s: ("🟢" if st["up"] else "🔴") + (" 🔄" if st["stalled"] else "") 
                       for s, st in summary.items() if st["enabled"]}
            log.info("Status: %s", statuses)

        except Exception as e:
            log.error("Check loop error: %s", e)

        time.sleep(args.interval)

    log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
