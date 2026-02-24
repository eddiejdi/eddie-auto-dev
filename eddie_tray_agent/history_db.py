"""
Banco de dados para histórico do Tray Agent.

Persistência: **PostgreSQL no homelab** (via DATABASE_URL).
Se o Postgres estiver indisponível, o agente DEVE falhar com erro.
SQLite NÃO é utilizado — nunca criar fallback sem aprovação explícita.

Armazena: eventos lock/unlock, leituras de clima, estados do ventilador,
comandos de voz executados, snapshots de dispositivos.
"""
import logging
import os
import time
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# ─── PostgreSQL (homelab) ─────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres",
)


# =====================================================================
# Connection helper
# =====================================================================

def _pg_conn():
    """Retorna conexão PostgreSQL para o homelab."""
    return psycopg2.connect(DATABASE_URL, connect_timeout=15)


# =====================================================================
# Schema
# =====================================================================

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS tray_screen_events (
    id          SERIAL PRIMARY KEY,
    event       TEXT NOT NULL,
    ts          DOUBLE PRECISION NOT NULL,
    details     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tray_climate_readings (
    id          SERIAL PRIMARY KEY,
    ts          DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION,
    humidity    DOUBLE PRECISION,
    weather     TEXT DEFAULT '',
    city        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tray_fan_states (
    id          SERIAL PRIMARY KEY,
    ts          DOUBLE PRECISION NOT NULL,
    state       TEXT NOT NULL,
    speed       INTEGER DEFAULT 0,
    mode        TEXT DEFAULT '',
    temperature DOUBLE PRECISION,
    humidity    DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS tray_voice_commands (
    id          SERIAL PRIMARY KEY,
    ts          DOUBLE PRECISION NOT NULL,
    raw_text    TEXT NOT NULL,
    parsed_cmd  TEXT DEFAULT '',
    success     INTEGER DEFAULT 0,
    response    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tray_device_snapshots (
    id          SERIAL PRIMARY KEY,
    ts          DOUBLE PRECISION NOT NULL,
    room        TEXT NOT NULL,
    device_name TEXT NOT NULL,
    state       TEXT NOT NULL,
    attributes  TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tray_screen_ts ON tray_screen_events(ts);
CREATE INDEX IF NOT EXISTS idx_tray_climate_ts ON tray_climate_readings(ts);
CREATE INDEX IF NOT EXISTS idx_tray_fan_ts ON tray_fan_states(ts);
CREATE INDEX IF NOT EXISTS idx_tray_voice_ts ON tray_voice_commands(ts);
CREATE INDEX IF NOT EXISTS idx_tray_snap_room ON tray_device_snapshots(room, device_name, ts);
"""


# =====================================================================
# Init
# =====================================================================

def init_db():
    """Cria tabelas no PostgreSQL do homelab. Falha se Postgres indisponível."""
    conn = _pg_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(_PG_SCHEMA)
    conn.close()
    logger.info(
        "🗄️  Persistência: PostgreSQL no homelab (%s)",
        DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "local",
    )


# =====================================================================
# Generic execute helper
# =====================================================================

def _execute(query: str, params: tuple = (), fetch: str = "none"):
    """
    Executa query no PostgreSQL.
    fetch: 'none' | 'one' | 'all'
    Queries usam %s como placeholder (Postgres style).
    """
    conn = _pg_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch == "one":
                    row = cur.fetchone()
                    return dict(row) if row else None
                elif fetch == "all":
                    return [dict(r) for r in cur.fetchall()]
                return None
    finally:
        conn.close()


# =====================================================================
# API — Screen events
# =====================================================================

def log_screen_event(event: str, details: str = ""):
    _execute(
        "INSERT INTO tray_screen_events (event, ts, details) VALUES (%s, %s, %s)",
        (event, time.time(), details),
    )


# =====================================================================
# API — Climate readings
# =====================================================================

def log_climate(temperature: float, humidity: float, weather: str = "", city: str = ""):
    _execute(
        "INSERT INTO tray_climate_readings (ts, temperature, humidity, weather, city) "
        "VALUES (%s, %s, %s, %s, %s)",
        (time.time(), temperature, humidity, weather, city),
    )


def get_climate_history(limit: int = 100) -> List[Dict[str, Any]]:
    return _execute(
        "SELECT * FROM tray_climate_readings ORDER BY ts DESC LIMIT %s",
        (limit,),
        fetch="all",
    ) or []


# =====================================================================
# API — Fan states
# =====================================================================

def log_fan_state(state: str, speed: int = 0, mode: str = "",
                  temperature: float = 0, humidity: float = 0):
    _execute(
        "INSERT INTO tray_fan_states (ts, state, speed, mode, temperature, humidity) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (time.time(), state, speed, mode, temperature, humidity),
    )


def get_last_fan_state() -> Optional[Dict[str, Any]]:
    """Retorna o último estado registrado do ventilador (quando ON)."""
    return _execute(
        "SELECT * FROM tray_fan_states WHERE state='on' ORDER BY ts DESC LIMIT 1",
        (),
        fetch="one",
    )


def get_fan_history(limit: int = 100) -> List[Dict[str, Any]]:
    return _execute(
        "SELECT * FROM tray_fan_states ORDER BY ts DESC LIMIT %s",
        (limit,),
        fetch="all",
    ) or []


# =====================================================================
# API — Voice commands
# =====================================================================

def log_voice_command(raw_text: str, parsed_cmd: str = "",
                      success: bool = False, response: str = ""):
    _execute(
        "INSERT INTO tray_voice_commands (ts, raw_text, parsed_cmd, success, response) "
        "VALUES (%s, %s, %s, %s, %s)",
        (time.time(), raw_text, parsed_cmd, int(success), response),
    )


# =====================================================================
# API — Device snapshots
# =====================================================================

def save_device_snapshot(room: str, device_name: str, state: str,
                         attributes: str = "{}"):
    """Salva snapshot do estado de um dispositivo antes do lock."""
    _execute(
        "INSERT INTO tray_device_snapshots (ts, room, device_name, state, attributes) "
        "VALUES (%s, %s, %s, %s, %s)",
        (time.time(), room, device_name, state, attributes),
    )


def get_last_snapshots(room: str) -> List[Dict[str, Any]]:
    """Retorna último snapshot de cada dispositivo da sala."""
    return _execute(
        """SELECT ds.*
           FROM tray_device_snapshots ds
           INNER JOIN (
               SELECT device_name, MAX(ts) as max_ts
               FROM tray_device_snapshots
               WHERE room = %s
               GROUP BY device_name
           ) latest ON ds.device_name = latest.device_name
                    AND ds.ts = latest.max_ts
           WHERE ds.room = %s""",
        (room, room),
        fetch="all",
    ) or []
