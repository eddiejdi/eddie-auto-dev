#!/usr/bin/env python3
"""Quick test for homelab persistence."""
import os
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgress:eddie_memory_2026@192.168.15.2:5433/postgres",
)

from eddie_tray_agent import history_db

history_db.init_db()
print("PostgreSQL connected: OK")

history_db.log_screen_event("test", "homelab persistence test")
print("write screen_event: OK")

history_db.log_climate(25.3, 68.0, "nublado", "Curitiba")
print("write climate: OK")

history_db.log_fan_state("on", speed=2, mode="normal", temperature=25.3, humidity=68.0)
print("write fan_state: OK")

fan = history_db.get_last_fan_state()
print(f"read fan: state={fan.get('state') if fan else None} speed={fan.get('speed') if fan else 0}")

climate = history_db.get_climate_history(3)
print(f"read climate: {len(climate)} records")

print("\nALL PERSISTENCE TESTS PASSED")
