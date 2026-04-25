#!/usr/bin/env python3
"""Converter: Playwright capture -> ytmusicapi headers_auth.json

Tentativa automatizada de extrair um bloco de headers úteis a partir
de uma captura Playwright/Selenium e passar para `ytmusicapi.setup`.

Saída:
 - .cache/ytmusic_headers_candidate.txt  (raw header lines)
 - .cache/headers_auth.json             (if ytmusicapi.setup aceitar)

Use quando: você tenha feito uma captura visível e queira tentar
reconstruir o `headers_auth.json` automaticamente.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def load_capture(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def find_best_headers(capture: Dict[str, Any]) -> Optional[Dict[str, str]]:
    # Prefer request entries that contain cookies or x-goog-authuser
    requests = capture.get("requests") or []
    def has_keys(hdrs, keys):
        if not hdrs:
            return False
        low = {k.lower() for k in hdrs.keys()}
        return any(k.lower() in low for k in keys)

    preferred_keys = ["cookie", "x-goog-authuser", "authorization", "x-youtube-identity-token"]

    for req in requests:
        hdrs = req.get("headers") or {}
        if has_keys(hdrs, preferred_keys):
            return hdrs

    # Fallback: choose first request to youtubei or verify_session
    for req in requests:
        url = (req.get("url") or "").lower()
        if "/youtubei/" in url or "verify_session" in url or "music.youtube.com" in url:
            return req.get("headers") or {}

    # As last resort, return first request headers
    if requests:
        return requests[0].get("headers") or {}
    return None


def build_header_lines(headers: Dict[str, str]) -> str:
    # Convert mapping into lines like copied from browser DevTools
    lines = []
    for k, v in headers.items():
        # Skip empty values
        if v is None:
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", default=".cache/ytmusic_playwright_capture.json")
    parser.add_argument("--out-headers", default=".cache/ytmusic_headers_candidate.txt")
    parser.add_argument("--out-json", default=".cache/headers_auth.json")
    args = parser.parse_args(argv)

    cap_path = Path(args.capture)
    if not cap_path.exists():
        print(f"Capture file not found: {cap_path}", file=sys.stderr)
        return 2

    try:
        capture = load_capture(cap_path)
    except Exception as e:
        print(f"Failed to read/parse capture: {e}", file=sys.stderr)
        return 3

    headers = find_best_headers(capture)
    if not headers:
        print("No headers found in capture.", file=sys.stderr)
        return 4

    header_lines = build_header_lines(headers)
    out_headers = Path(args.out_headers)
    out_headers.parent.mkdir(parents=True, exist_ok=True)
    out_headers.write_text(header_lines, encoding="utf-8")
    print(f"Wrote candidate headers to: {out_headers}")

    # Try to hand off to ytmusicapi.setup for parsing and file creation
    try:
        import importlib

        print("Attempting ytmusicapi.setup with extracted headers...")
        setup_mod = importlib.import_module("ytmusicapi.setup")
        # Call the setup helper which wraps setup_browser
        setup_mod.setup(filepath=args.out_json, headers_raw=header_lines)
        print("ytmusicapi.setup returned. Headers file created at:", args.out_json)
        return 0
    except Exception as e:  # pragma: no cover - runtime behavior
        print("ytmusicapi.setup failed:", str(e), file=sys.stderr)
        print("You can inspect the candidate headers at:", out_headers)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
