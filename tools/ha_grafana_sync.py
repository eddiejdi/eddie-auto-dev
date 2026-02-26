#!/usr/bin/env python3
"""
ha_grafana_sync.py — Sincroniza entidades do Home Assistant → PostgreSQL
para alimentar o dashboard Grafana de automação residencial.

Tabelas:
  - home_devices: estado atual de cada dispositivo
  - home_device_history: histórico de mudanças de estado

Roda no homelab via cron ou systemd timer a cada 30s.

Uso:
  python3 ha_grafana_sync.py              # sync uma vez
  python3 ha_grafana_sync.py --loop 30    # loop contínuo (30s)
  python3 ha_grafana_sync.py --init       # cria tabelas + sync
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERRO: instale psycopg2-binary: pip install psycopg2-binary")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERRO: instale requests: pip install requests")
    sys.exit(1)

# ──────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────

HA_URL = os.getenv("HA_URL", "http://localhost:8123")
HA_TOKEN = os.getenv(
    "HA_TOKEN",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiI2M2Q5NmE1MDI2YmU0YzM0ODRiNTM3Mjk2ODkxN2U5MiIsImlhdCI6MTc3MTg5NTI5MCwiZXhwIjoxODAzNDMxMjkwfQ."
    "3eTEElWAUf3mTxQ9A0HvqBEvctRlVtGOuj0DhfehCHM",
)
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "postgress")
DB_USER = os.getenv("PGUSER", "postgress")
DB_PASS = os.getenv("PGPASSWORD", "postgress")

# Domínios relevantes (os que aparecem no dashboard)
RELEVANT_DOMAINS = {"switch", "light", "fan", "media_player", "climate", "sensor"}

# Somente sensores de energia/bateria (excluir sensores de timestamp/backup)
SENSOR_WHITELIST_CLASSES = {"energy", "power", "battery", "temperature", "humidity"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ha_grafana_sync")

# ──────────────────────────────────────────────────────────
# Entity → room/device_type mapping
# ──────────────────────────────────────────────────────────

# Mapeamento manual de entity_id → room (baseado nos nomes Tuya)
ROOM_MAP: dict[str, str] = {
    # Escritório
    "fan.ventilador_e_luz": "Escritório",
    "light.luz_backlight": "Escritório",
    "switch.luz_switch_1": "Escritório",
    "switch.luz_switch_2": "Escritório",
    "switch.luz_switch_3": "Escritório",
    "switch.esteira_switch_1": "Escritório",
    "sensor.esteira_total_energy": "Escritório",
    "media_player.trailer": "Escritório",
    # Sala
    "light.luz_backlight_2": "Sala",
    "switch.luz_switch_1_2": "Sala",
    "switch.luz_switch_2_2": "Sala",
    "switch.luz_switch_3_2": "Sala",
    "switch.aquario_socket_1": "Sala",
    "switch.aquario_child_lock": "Sala",
    "switch.luz_aquario_socket_1": "Sala",
    "switch.luz_aquario_child_lock": "Sala",
    "sensor.aquario_total_energy": "Sala",
    "sensor.luz_aquario_total_energy": "Sala",
    "media_player.tv_sala": "Sala",
    # Quarto
    "fan.quarto": "Quarto",
    "light.quarto": "Quarto",
    # Quarto Júlia
    "light.luz_julia_backlight": "Quarto Júlia",
    "switch.luz_julia_switch_1": "Quarto Júlia",
    # Geral / Infraestrutura
    "switch.wifi_breaker_socket_1": "Infraestrutura",
    "switch.wifi_breaker_child_lock": "Infraestrutura",
    "binary_sensor.sensor_de_movimento_motion": "Sala",
    "sensor.sensor_de_movimento_battery_state": "Sala",
}

# domain → device_type para o dashboard
DOMAIN_TO_TYPE: dict[str, str] = {
    "switch": "switch",
    "light": "light",
    "fan": "fan",
    "media_player": "tv",
    "climate": "air_conditioner",
    "sensor": "sensor",
    "binary_sensor": "sensor",
}

# Manufacturer por integração (HA template já retorna isso)
MANUFACTURER_MAP: dict[str, str] = {
    "tuya": "Tuya",
    "cast": "Google Inc.",
    "homeassistant": "Home Assistant",
}


def _guess_room(entity_id: str) -> str:
    """Infere o cômodo pelo nome da entidade se não estiver no mapa."""
    if entity_id in ROOM_MAP:
        return ROOM_MAP[entity_id]
    eid = entity_id.lower()
    if "julia" in eid:
        return "Quarto Júlia"
    if "quarto" in eid:
        return "Quarto"
    if "sala" in eid:
        return "Sala"
    if "aquario" in eid:
        return "Sala"
    if "esteira" in eid or "escritorio" in eid:
        return "Escritório"
    return "Outros"


def _guess_device_type(entity_id: str, domain: str, attrs: dict) -> str:
    """Infere o tipo de dispositivo."""
    dc = attrs.get("device_class", "")
    if dc == "outlet":
        return "plug"
    return DOMAIN_TO_TYPE.get(domain, "switch")


def _should_include_sensor(entity_id: str, state: str, attrs: dict) -> bool:
    """Filtra sensores relevantes (energia, bateria, temperatura)."""
    dc = attrs.get("device_class", "")
    # Incluir sensores com device_class relevante
    if dc in SENSOR_WHITELIST_CLASSES:
        return True
    # Incluir sensores de energia pelo nome
    if "energy" in entity_id or "battery" in entity_id:
        return True
    return False


# ──────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS home_devices (
    id              TEXT PRIMARY KEY,
    entity_id       TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    device_type     TEXT NOT NULL DEFAULT 'switch',
    room            TEXT NOT NULL DEFAULT 'Outros',
    state           TEXT NOT NULL DEFAULT 'unknown',
    ip_address      TEXT DEFAULT '',
    manufacturer    TEXT DEFAULT '',
    category        TEXT DEFAULT 'tuya',
    percentage      INTEGER DEFAULT NULL,
    attributes      JSONB DEFAULT '{}'::jsonb,
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS home_device_history (
    id              SERIAL PRIMARY KEY,
    device_id       TEXT REFERENCES home_devices(id) ON DELETE CASCADE,
    device_name     TEXT NOT NULL,
    action          TEXT NOT NULL,
    old_state       TEXT DEFAULT '',
    new_state       TEXT DEFAULT '',
    source          TEXT DEFAULT 'ha_sync',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_home_devices_room ON home_devices(room);
CREATE INDEX IF NOT EXISTS idx_home_devices_type ON home_devices(device_type);
CREATE INDEX IF NOT EXISTS idx_home_devices_state ON home_devices(state);
CREATE INDEX IF NOT EXISTS idx_home_history_created ON home_device_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_home_history_device ON home_device_history(device_id);
"""


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )


def init_tables(conn):
    with conn.cursor() as cur:
        cur.execute(DDL)
        # Compat: adicionar colunas que podem não existir em esquemas antigos
        try:
            cur.execute("ALTER TABLE home_devices ADD COLUMN IF NOT EXISTS percentage INTEGER DEFAULT NULL")
            cur.execute("ALTER TABLE home_devices ADD COLUMN IF NOT EXISTS attributes JSONB DEFAULT '{}'::jsonb")
        except Exception:
            # algumas versões do Postgres/psycopg2 podem não suportar IF NOT EXISTS em ALTER TABLE
            pass
    conn.commit()
    logger.info("Tabelas home_devices e home_device_history criadas/verificadas")


# ──────────────────────────────────────────────────────────
# HA API
# ──────────────────────────────────────────────────────────

def fetch_ha_states() -> list[dict[str, Any]]:
    """Busca todos os estados do Home Assistant."""
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.get(f"{HA_URL}/api/states", headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_ha_device_info(entity_id: str) -> dict[str, str]:
    """Busca info do dispositivo via template API."""
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    template = (
        f'{{"template": "{{{{ device_attr(\'{entity_id}\', \'manufacturer\') }}}}'
        f"|{{{{ device_attr('{entity_id}', 'model') }}}}"
        f"|{{{{ device_attr('{entity_id}', 'sw_version') }}}}\"}}"
    )
    try:
        resp = requests.post(
            f"{HA_URL}/api/template",
            headers=headers,
            data=template,
            timeout=5,
        )
        if resp.ok:
            parts = resp.text.strip().split("|")
            return {
                "manufacturer": parts[0] if parts[0] != "None" else "",
                "model": parts[1] if len(parts) > 1 and parts[1] != "None" else "",
            }
    except Exception:
        pass
    return {"manufacturer": "", "model": ""}


# ──────────────────────────────────────────────────────────
# Sync logic
# ──────────────────────────────────────────────────────────

def sync(conn) -> int:
    """Sincroniza estados do HA → PostgreSQL. Retorna count de dispositivos."""
    states = fetch_ha_states()
    now = datetime.now(timezone.utc)

    # Filtrar entidades relevantes
    devices: list[dict] = []
    for s in states:
        eid = s["entity_id"]
        domain = eid.split(".")[0]

        if domain not in RELEVANT_DOMAINS:
            continue

        state = s["state"]
        attrs = s.get("attributes", {})
        friendly = attrs.get("friendly_name", eid)

        # Filtrar sensores irrelevantes (backup, sun, etc.)
        if domain == "sensor" and not _should_include_sensor(eid, state, attrs):
            continue

        # Excluir child_lock e selects auxiliares
        if "child_lock" in eid:
            continue

        room = _guess_room(eid)
        device_type = _guess_device_type(eid, domain, attrs)
        device_info = fetch_ha_device_info(eid)
        manufacturer = device_info.get("manufacturer", "")

        # Category: tuya, cast, ha
        category = "tuya"
        if manufacturer == "Google Inc.":
            category = "cast"
        elif manufacturer == "Home Assistant":
            category = "ha"

        # Normalizar estado
        if state == "unavailable":
            normalized_state = "unavailable"
        elif state in ("on", "playing", "home"):
            normalized_state = "on"
        elif state in ("off", "idle", "standby", "paused"):
            normalized_state = "off"
        else:
            normalized_state = state

        devices.append({
            "id": eid.replace(".", "_"),
            "entity_id": eid,
            "name": friendly,
            "device_type": device_type,
            "room": room,
            "state": normalized_state,
            "percentage": attrs.get("percentage"),
            "attributes": json.dumps(attrs),
            "ip_address": attrs.get("ip_address", ""),
            "manufacturer": manufacturer,
            "category": category,
            "last_updated": now,
        })

    if not devices:
        logger.warning("Nenhum dispositivo relevante encontrado no HA")
        return 0

    # Buscar estados atuais para detectar mudanças (history)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, state, name FROM home_devices")
        existing = {r["id"]: r for r in cur.fetchall()}

    # Upsert dispositivos
    upsert_sql = """
        INSERT INTO home_devices (id, entity_id, name, device_type, room, state,
                       ip_address, manufacturer, category, percentage, attributes, last_updated)
        VALUES (%(id)s, %(entity_id)s, %(name)s, %(device_type)s, %(room)s, %(state)s,
            %(ip_address)s, %(manufacturer)s, %(category)s, %(percentage)s, %(attributes)s::jsonb, %(last_updated)s)
        ON CONFLICT (id) DO UPDATE SET
            state = EXCLUDED.state,
            name = EXCLUDED.name,
            last_updated = EXCLUDED.last_updated,
            percentage = COALESCE(EXCLUDED.percentage, home_devices.percentage),
            manufacturer = CASE WHEN EXCLUDED.manufacturer != '' THEN EXCLUDED.manufacturer
                               ELSE home_devices.manufacturer END,
            attributes = COALESCE(EXCLUDED.attributes, home_devices.attributes)
    """

    history_sql = """
        INSERT INTO home_device_history (device_id, device_name, action, old_state, new_state, source, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    with conn.cursor() as cur:
        for dev in devices:
            cur.execute(upsert_sql, dev)

            # Detectar mudança de estado → registrar histórico
            old = existing.get(dev["id"])
            if old and old["state"] != dev["state"]:
                action = dev["state"]  # on, off, unavailable
                cur.execute(history_sql, (
                    dev["id"],
                    dev["name"],
                    action,
                    old["state"],
                    dev["state"],
                    "ha_sync",
                    now,
                ))
                logger.info(
                    "📝 %s: %s → %s",
                    dev["name"], old["state"], dev["state"],
                )

    conn.commit()
    logger.info("✅ Sync: %d dispositivos atualizados", len(devices))
    return len(devices)


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HA → PostgreSQL sync para Grafana")
    parser.add_argument("--init", action="store_true", help="Criar tabelas")
    parser.add_argument("--loop", type=int, default=0, help="Loop contínuo (segundos)")
    args = parser.parse_args()

    conn = get_conn()

    if args.init:
        init_tables(conn)

    # Garantir que as tabelas existem
    init_tables(conn)

    if args.loop > 0:
        logger.info("🔄 Loop contínuo a cada %ds", args.loop)
        while True:
            try:
                sync(conn)
            except Exception as exc:
                logger.error("Erro no sync: %s", exc)
                # Reconectar se necessário
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    conn = get_conn()
                except Exception as exc2:
                    logger.error("Erro ao reconectar: %s", exc2)
            time.sleep(args.loop)
    else:
        count = sync(conn)
        print(f"Sync completo: {count} dispositivos")

    conn.close()


if __name__ == "__main__":
    main()
