#!/usr/bin/env python3
"""
Setup PostgreSQL tables for Grafana Home Automation dashboard
and sync current device state.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import execute_values
import requests

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgress:eddie_memory_2026@localhost:55432/postgres")
API_URL = "http://localhost:8503"

def setup_tables(conn):
    """Create home automation tables for Grafana."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS home_devices (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        device_type TEXT NOT NULL DEFAULT 'custom',
        room TEXT NOT NULL DEFAULT 'default',
        state TEXT NOT NULL DEFAULT 'unknown',
        category TEXT NOT NULL DEFAULT 'unknown',
        manufacturer TEXT DEFAULT '',
        ip_address TEXT DEFAULT '',
        brightness INT,
        temperature FLOAT,
        last_updated TIMESTAMP DEFAULT NOW(),
        attributes JSONB DEFAULT '{}'::jsonb
    );

    CREATE TABLE IF NOT EXISTS home_device_history (
        id SERIAL PRIMARY KEY,
        device_id TEXT NOT NULL,
        device_name TEXT NOT NULL,
        action TEXT NOT NULL,
        old_state TEXT,
        new_state TEXT,
        source TEXT DEFAULT 'api',
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS home_command_queue (
        id SERIAL PRIMARY KEY,
        device_id TEXT NOT NULL,
        command TEXT NOT NULL,
        params JSONB DEFAULT '{}'::jsonb,
        status TEXT DEFAULT 'pending',
        result JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        executed_at TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_home_devices_room ON home_devices(room);
    CREATE INDEX IF NOT EXISTS idx_home_devices_type ON home_devices(device_type);
    CREATE INDEX IF NOT EXISTS idx_home_devices_state ON home_devices(state);
    CREATE INDEX IF NOT EXISTS idx_home_history_device ON home_device_history(device_id);
    CREATE INDEX IF NOT EXISTS idx_home_history_created ON home_device_history(created_at);
    CREATE INDEX IF NOT EXISTS idx_home_command_status ON home_command_queue(status);
    """)
    conn.commit()
    print("OK: Tables created")

def sync_devices(conn):
    """Sync devices from API to PostgreSQL."""
    cur = conn.cursor()
    
    resp = requests.get(f"{API_URL}/home/devices", timeout=10)
    devices = resp.json()
    
    for dev in devices:
        attrs = dev.get("attributes", {})
        cur.execute("""
        INSERT INTO home_devices (id, name, device_type, room, state, category, manufacturer,
                                   ip_address, brightness, temperature, last_updated, attributes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            device_type = EXCLUDED.device_type,
            room = EXCLUDED.room,
            state = EXCLUDED.state,
            category = EXCLUDED.category,
            manufacturer = EXCLUDED.manufacturer,
            ip_address = EXCLUDED.ip_address,
            brightness = EXCLUDED.brightness,
            temperature = EXCLUDED.temperature,
            last_updated = NOW(),
            attributes = EXCLUDED.attributes
        """, (
            dev["id"],
            dev["name"],
            dev["device_type"],
            dev["room"],
            dev["state"],
            attrs.get("category", "unknown"),
            attrs.get("manufacturer", ""),
            attrs.get("host", ""),
            dev.get("brightness"),
            dev.get("temperature"),
            json.dumps(attrs),
        ))
    
    conn.commit()
    print(f"OK: Synced {len(devices)} devices to PostgreSQL")

def main():
    conn = psycopg2.connect(DB_URL)
    setup_tables(conn)
    sync_devices(conn)
    
    # Verify
    cur = conn.cursor()
    cur.execute("SELECT id, name, device_type, room, state, category, ip_address FROM home_devices ORDER BY name")
    rows = cur.fetchall()
    print(f"\nDevices in PostgreSQL ({len(rows)}):")
    for r in rows:
        print(f"  {r[1]:25s} | {r[2]:8s} | {r[3]:12s} | {r[4]:8s} | {r[5]:12s} | {r[6]}")
    
    conn.close()

if __name__ == "__main__":
    main()
