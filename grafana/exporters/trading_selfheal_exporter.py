#!/usr/bin/env python3
"""Prometheus exporter + self-healing para trading agents multi-coin.

Monitora 6 moedas (BTC, ETH, XRP, SOL, DOGE, ADA) com detecção inteligente de stalls
usando Ollama (llm-optimizer @ 8512) + health checks multi-camada + auto-restart.

Usage:
  python3 trading_selfheal_exporter.py --port 9120 --config trading_selfheal_config.json

Metrics:
  trading_agent_up{symbol}                          — 1=healthy, 0=down
  trading_agent_stalled{symbol}                      — 1=stalled (alive but no decisions), 0=ok
  trading_agent_last_decision_age_seconds{symbol}    — time since last decision
  trading_agent_restart_total{symbol}                — counter of auto-restarts
  trading_agent_consecutive_failures{symbol}         — failed health checks in a row
  trading_selfheal_actions_total{action}             — total self-heal actions
  trading_agent_ollama_stall_confidence{symbol}      — Ollama confidence of stall (0-1)

Systemd service: trading-selfheal-exporter.service
Self-healing: restarts crypto-agent@* when stalled (max 3/hour, 60s cooldown)
Ollama integration: uses local Ollama @ 8512 for intelligent stall analysis
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import psycopg2
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from prometheus_client import Counter, Gauge, start_http_server
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
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://192.168.15.2:8512")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
PG_DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres"
)

# ── Trading Agent Definitions ──────────────────────────────────────────

@dataclass
class TradingAgentDef:
    """Definition of a trading agent to monitor."""
    symbol: str  # BTC-USDT, ETH-USDT, etc.
    systemd_unit: str  # crypto-agent@BTC_USDT.service
    exporter_port: int  # 9092, 9093, etc.
    config_file: str  # config_BTC_USDT.json
    expected_process: str  # pgrep pattern
    enabled: bool = True


DEFAULT_AGENTS: List[TradingAgentDef] = [
    TradingAgentDef(
        symbol="BTC-USDT",
        systemd_unit="crypto-agent@BTC_USDT.service",
        exporter_port=9092,
        config_file="config_BTC_USDT.json",
        expected_process="trading_agent.py.*BTC_USDT",
    ),
    TradingAgentDef(
        symbol="ETH-USDT",
        systemd_unit="crypto-agent@ETH_USDT.service",
        exporter_port=9093,
        config_file="config_ETH_USDT.json",
        expected_process="trading_agent.py.*ETH_USDT",
    ),
    TradingAgentDef(
        symbol="XRP-USDT",
        systemd_unit="crypto-agent@XRP_USDT.service",
        exporter_port=9094,
        config_file="config_XRP_USDT.json",
        expected_process="trading_agent.py.*XRP_USDT",
    ),
    TradingAgentDef(
        symbol="SOL-USDT",
        systemd_unit="crypto-agent@SOL_USDT.service",
        exporter_port=9095,
        config_file="config_SOL_USDT.json",
        expected_process="trading_agent.py.*SOL_USDT",
    ),
    TradingAgentDef(
        symbol="DOGE-USDT",
        systemd_unit="crypto-agent@DOGE_USDT.service",
        exporter_port=9096,
        config_file="config_DOGE_USDT.json",
        expected_process="trading_agent.py.*DOGE_USDT",
    ),
    TradingAgentDef(
        symbol="ADA-USDT",
        systemd_unit="crypto-agent@ADA_USDT.service",
        exporter_port=9097,
        config_file="config_ADA_USDT.json",
        expected_process="trading_agent.py.*ADA_USDT",
    ),
]


def load_agent_config(config_path: str) -> List[TradingAgentDef]:
    """Load agent definitions from JSON file, falling back to defaults."""
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                data = json.load(f)
            agents = []
            for a in data.get("agents", []):
                agents.append(TradingAgentDef(**a))
            log.info("Loaded %d agent definitions from %s", len(agents), config_path)
            return agents
        except Exception as e:
            log.warning("Failed to load config %s: %s — using defaults", config_path, e)
    return DEFAULT_AGENTS


# ── Agent State Tracking ───────────────────────────────────────────────

@dataclass
class AgentState:
    up: bool = False
    stalled: bool = False
    last_check: float = 0
    consecutive_failures: int = 0
    restarts_this_hour: int = 0
    restarts_total: int = 0
    last_restart: float = 0
    last_decision_age: float = 0
    ollama_stall_confidence: float = 0.0
    hour_window_start: float = 0
    ollama_reasoning: str = ""


# ── Ollama Integration ─────────────────────────────────────────────────

def query_ollama(prompt: str) -> Tuple[bool, str]:
    """Query Ollama for analysis. Returns (success, response_text)."""
    try:
        req_data = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "3600s",  # Keep model in memory 1h
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=req_data,
            headers={"Content-Type": "application/json"},
        )
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return True, result.get("response", "").strip()
    except Exception as e:
        log.warning("Ollama query failed: %s", e)
        return False, ""


def analyze_stall_with_ollama(symbol: str, age_seconds: float, last_reasons: str) -> Tuple[float, str]:
    """Use Ollama to analyze if agent is truly stalled. 
    Returns (confidence_0_to_1, reasoning_text).
    """
    prompt = f"""Analyze if a trading agent is stalled based on this data:
    
Symbol: {symbol}
Last Decision Age: {age_seconds} seconds
Stall Threshold: {STALL_THRESHOLD} seconds
Last Log Reasons: {last_reasons[:200]}

Is the agent stalled (alive but not producing decisions)? Respond with confidence 0-1.
Be concise (1-2 sentences max).
Format: "CONFIDENCE: X.X | REASON: ..."
"""
    
    success, response = query_ollama(prompt)
    if not success:
        # Fallback: use simple threshold
        conf = min(1.0, age_seconds / STALL_THRESHOLD)
        return conf, f"Fallback threshold: {age_seconds}s vs {STALL_THRESHOLD}s → {conf:.2f}"
    
    # Parse response
    try:
        lines = response.split("|")
        conf_str = lines[0].split(":")[1].strip() if len(lines) > 0 else "0.5"
        reason = lines[1].split(":")[1].strip() if len(lines) > 1 else "Ollama analysis"
        conf = float(conf_str)
        return min(1.0, max(0.0, conf)), reason
    except Exception:
        return 0.5, f"Parse error: {response[:100]}"


# ── Health Check Engine ────────────────────────────────────────────────

class AgentHealthChecker:
    """Checks agent health and performs self-healing restarts."""

    def __init__(self, agents: List[TradingAgentDef], pg_dsn: str):
        self.agents = {a.symbol: a for a in agents}
        self.states: Dict[str, AgentState] = {a.symbol: AgentState() for a in agents}
        self._lock = threading.Lock()
        self.pg_dsn = pg_dsn
        self._pg_conn = None

    def _ensure_pg_conn(self):
        """Ensure PostgreSQL connection is open."""
        try:
            if self._pg_conn is None or self._pg_conn.closed:
                self._pg_conn = psycopg2.connect(self.pg_dsn)
                self._pg_conn.autocommit = True
        except Exception as e:
            log.error("PostgreSQL connection error: %s", e)
            self._pg_conn = None

    def check_systemd_active(self, unit: str) -> bool:
        """Check if systemd unit is active."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    def check_process(self, pattern: str) -> bool:
        """Check if process matching pattern is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_last_decision_age(self, symbol: str) -> Optional[float]:
        """Query PostgreSQL for time since last decision."""
        try:
            self._ensure_pg_conn()
            if self._pg_conn is None:
                return None
            
            cur = self._pg_conn.cursor()
            cur.execute("SET search_path TO btc, public")
            cur.execute(
                "SELECT MAX(timestamp) FROM btc.decisions WHERE symbol=%s",
                (symbol,)
            )
            result = cur.fetchone()
            if result and result[0]:
                age = time.time() - result[0]
                return age
            return None
        except Exception as e:
            log.warning("Failed to query last decision for %s: %s", symbol, e)
            return None

    def restart_service(self, agent: TradingAgentDef, state: AgentState) -> bool:
        """Restart a systemd service with rate limiting."""
        now = time.time()

        # Reset hourly counter if window expired
        if now - state.hour_window_start > 3600:
            state.restarts_this_hour = 0
            state.hour_window_start = now

        # Rate limit
        if state.restarts_this_hour >= MAX_RESTARTS_PER_HOUR:
            log.warning(
                "RATE LIMIT: %s already restarted %d times this hour — skipping",
                agent.symbol, state.restarts_this_hour,
            )
            self._audit("rate_limited", agent.symbol, False,
                       f"Exceeded {MAX_RESTARTS_PER_HOUR} restarts/hour")
            return False

        # Cooldown
        if now - state.last_restart < COOLDOWN_AFTER_RESTART:
            log.info("COOLDOWN: %s restarted recently — waiting", agent.symbol)
            return False

        log.warning("SELF-HEAL: restarting %s (%s)", agent.symbol, agent.systemd_unit)
        cmd = f"systemctl restart {agent.systemd_unit}"
        try:
            result = subprocess.run(
                cmd.split(), capture_output=True, text=True, timeout=30,
            )
            success = result.returncode == 0
            state.last_restart = now
            state.restarts_this_hour += 1
            state.restarts_total += 1
            self._audit("restart", agent.symbol, success, result.stderr.strip())
            if success:
                log.info("SELF-HEAL: %s restarted successfully", agent.symbol)
            else:
                log.error("SELF-HEAL: %s restart FAILED: %s", agent.symbol, result.stderr)
            return success
        except Exception as e:
            log.error("SELF-HEAL: %s restart EXCEPTION: %s", agent.symbol, e)
            self._audit("restart", agent.symbol, False, str(e))
            return False

    def check_agent(self, symbol: str) -> bool:
        """Run all health checks for an agent. Returns True if healthy."""
        agent = self.agents[symbol]
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
        if systemd_ok:
            proc_ok = self.check_process(agent.expected_process)
            checks.append(("process", proc_ok))
        else:
            checks.append(("process", False))

        # 3. Stall detection (DB query + Ollama analysis)
        stalled = False
        age = self.get_last_decision_age(symbol)
        if age is not None:
            state.last_decision_age = age
            # Use Ollama for intelligent stall detection
            conf, reasoning = analyze_stall_with_ollama(symbol, age, "")
            state.ollama_stall_confidence = conf
            state.ollama_reasoning = reasoning
            stalled = conf > 0.7  # Stalled if confidence > 70%
        
        state.stalled = stalled
        checks.append(("stalled", not stalled))

        # Determine overall health — systemd + process + not stalled
        all_ok = all(ok for _, ok in checks) and len(checks) > 0
        state.last_check = time.time()

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
                self.restart_service(agent, state)

        return all_ok

    def check_all(self):
        """Run checks on all agents."""
        for symbol in self.agents:
            try:
                self.check_agent(symbol)
            except Exception as e:
                log.error("CHECK ERROR for %s: %s", symbol, e)

    def get_summary(self) -> Dict:
        """Return current state summary."""
        result = {}
        for symbol, state in self.states.items():
            agent = self.agents[symbol]
            result[symbol] = {
                "enabled": agent.enabled,
                "up": state.up,
                "stalled": state.stalled,
                "consecutive_failures": state.consecutive_failures,
                "restarts_total": state.restarts_total,
                "restarts_this_hour": state.restarts_this_hour,
                "last_decision_age_seconds": state.last_decision_age,
                "ollama_stall_confidence": state.ollama_stall_confidence,
                "ollama_reasoning": state.ollama_reasoning,
                "last_check": datetime.fromtimestamp(
                    state.last_check, tz=timezone.utc
                ).isoformat() if state.last_check else None,
            }
        return result

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


# ── Prometheus Metrics ─────────────────────────────────────────────────

def setup_prometheus_metrics():
    """Create Prometheus metric objects."""
    if not HAS_PROM:
        return None

    metrics = {
        "up": Gauge(
            "trading_agent_up", "Agent health status (1=up, 0=down)",
            ["symbol"],
        ),
        "stalled": Gauge(
            "trading_agent_stalled", "Agent stalled status (1=stalled, 0=ok)",
            ["symbol"],
        ),
        "last_decision_age": Gauge(
            "trading_agent_last_decision_age_seconds", "Seconds since last decision",
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
        "ollama_confidence": Gauge(
            "trading_agent_ollama_stall_confidence", "Ollama stall confidence (0-1)",
            ["symbol"],
        ),
        "selfheal_actions": Counter(
            "trading_selfheal_actions_total", "Total self-healing actions",
            ["action"],
        ),
    }
    return metrics


def update_prometheus(checker: AgentHealthChecker, prom_metrics: dict):
    """Push current state to Prometheus gauges/counters."""
    if not prom_metrics:
        return
    for symbol, state in checker.states.items():
        prom_metrics["up"].labels(symbol=symbol).set(1 if state.up else 0)
        prom_metrics["stalled"].labels(symbol=symbol).set(1 if state.stalled else 0)
        prom_metrics["last_decision_age"].labels(symbol=symbol).set(
            state.last_decision_age if state.last_decision_age else 0
        )
        prom_metrics["consecutive_failures"].labels(symbol=symbol).set(
            state.consecutive_failures
        )
        prom_metrics["ollama_confidence"].labels(symbol=symbol).set(
            state.ollama_stall_confidence
        )
        # Counter: increment by delta since last update
        restart_counter = prom_metrics["restart_total"].labels(symbol=symbol)
        current_val = restart_counter._value.get()
        if state.restarts_total > current_val:
            restart_counter.inc(state.restarts_total - current_val)


# ── HTTP Status Endpoint ───────────────────────────────────────────────

class StatusHandler(BaseHTTPRequestHandler):
    checker: AgentHealthChecker = None

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


# ── Main Loop ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Trading agent health-check + self-healing exporter (with Ollama)"
    )
    parser.add_argument("--port", type=int, default=9120, help="Prometheus metrics port")
    parser.add_argument("--status-port", type=int, default=9121, help="HTTP status/audit port")
    parser.add_argument("--config", type=str, default="", help="Path to agents JSON config")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL, help="Check interval (s)")
    parser.add_argument("--dry-run", action="store_true", help="Check but don't restart")
    args = parser.parse_args()

    agents = load_agent_config(args.config)
    checker = AgentHealthChecker(agents, PG_DSN)

    # Prometheus
    prom_metrics = None
    if HAS_PROM:
        prom_metrics = setup_prometheus_metrics()
        start_http_server(args.port)
        log.info("Prometheus metrics on :%d", args.port)
    else:
        log.warning("prometheus_client not installed — metrics disabled")

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

    log.info("Starting trading agent health-check loop (interval=%ds, dry_run=%s)",
            args.interval, args.dry_run)
    log.info("Monitoring %d agents: %s",
            len(agents), [a.symbol for a in agents if a.enabled])
    log.info("Ollama integration: %s (model=%s)", OLLAMA_HOST, OLLAMA_MODEL)

    if args.dry_run:
        original_restart = checker.restart_service
        def noop_restart(agent, state):
            log.info("DRY-RUN: would restart %s", agent.symbol)
            return False
        checker.restart_service = noop_restart

    while running:
        try:
            checker.check_all()
            if prom_metrics:
                update_prometheus(checker, prom_metrics)

            # Log summary periodically
            summary = checker.get_summary()
            statuses = {
                n: ("UP" if s["up"] else "DOWN") + ("(STALLED)" if s["stalled"] else "")
                for n, s in summary.items() if n in checker.agents
            }
            log.info("Status: %s", statuses)

        except Exception as e:
            log.error("Check loop error: %s", e)

        time.sleep(args.interval)

    log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
