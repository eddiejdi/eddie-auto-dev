#!/usr/bin/env python3
"""Write a mock Diretor response to /tmp/diretor_response.json for testing.

Usage: python3 tools/force_diretor_response.py [--delay 2] [--content "approved"]
"""

import argparse
import time
import json
from datetime import datetime

OUT = "/tmp/diretor_response.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--content", type=str, default="approve")
    args = p.parse_args()
    time.sleep(args.delay)
    payload = {
        "id": "mock_" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "DIRETOR",
        "target": "assistant",
        "content": args.content,
        "metadata": {"mock": True},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
