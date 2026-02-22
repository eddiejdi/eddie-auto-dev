#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path

from openwebui_integration import get_integration_client

OUT = Path('/var/www/rpa4all.com/openwebui-models.json')


async def main():
    client = get_integration_client()
    try:
        status = await client.get_full_status()
        roster = status.get('model_roster', [])
        OUT.write_text(json.dumps({'model_roster': roster}, indent=2, ensure_ascii=False))
        print('wrote', OUT)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
