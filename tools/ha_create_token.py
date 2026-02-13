#!/usr/bin/env python3
"""Create a long-lived access token for Home Assistant via WebSocket API."""
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

HA_URL = "ws://localhost:8123/api/websocket"
ACCESS_TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""

async def create_long_lived_token():
    if not ACCESS_TOKEN:
        print("Usage: python3 ha_create_token.py <access_token>")
        sys.exit(1)

    async with websockets.connect(HA_URL) as ws:
        # 1. Receive auth_required
        msg = json.loads(await ws.recv())
        print(f"[1] {msg['type']}")
        assert msg["type"] == "auth_required"

        # 2. Send auth
        await ws.send(json.dumps({"type": "auth", "access_token": ACCESS_TOKEN}))
        msg = json.loads(await ws.recv())
        print(f"[2] {msg['type']}")
        if msg["type"] != "auth_ok":
            print(f"Auth failed: {msg}")
            sys.exit(1)

        # 3. Create long-lived token
        await ws.send(json.dumps({
            "id": 1,
            "type": "auth/long_lived_access_token",
            "client_name": "Eddie Auto Dev",
            "lifespan": 365
        }))
        msg = json.loads(await ws.recv())
        print(f"[3] Result: {msg}")

        if msg.get("success"):
            token = msg["result"]
            print(f"\n=== LONG-LIVED TOKEN ===")
            print(token)
            print(f"========================")
            return token
        else:
            print(f"Failed: {msg}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(create_long_lived_token())
