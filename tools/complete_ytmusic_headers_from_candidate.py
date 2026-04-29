#!/usr/bin/env python3
"""Helper: completar headers candidatos do YouTube Music

Lê um arquivo de headers candidatos (linhas `Key: Value`), detecta
se `cookie` e `x-goog-authuser` estão ausentes e permite fornecê-los
via argumentos. Opcionalmente tenta invocar `ytmusicapi.setup` para
gerar o `headers_auth.json` final.

Uso:
  python tools/complete_ytmusic_headers_from_candidate.py --candidate .cache/ytmusic_headers_candidate_from_authentik.txt \
    --cookie "<cookie header>" --xgoog 0 --out-json .cache/headers_auth.json --attempt-setup
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional


def load_candidate(path: Path) -> Dict[str, str]:
    """Carrega linhas `Key: Value` em um dict de headers."""
    text = path.read_text(encoding="utf-8")
    headers: Dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip()] = v.strip()
    return headers


def build_header_lines(headers: Dict[str, str]) -> List[str]:
    """Retorna linhas formatadas para ytmusicapi.setup (Key: Value)."""
    lines: List[str] = []
    for k, v in headers.items():
        lines.append(f"{k}: {v}")
    return lines


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Completa headers candidatos do ytmusic e tenta gerar headers_auth.json")
    parser.add_argument("--candidate", default=".cache/ytmusic_headers_candidate_from_authentik.txt")
    parser.add_argument("--cookie", default=None, help="Valor completo do header Cookie (se ausente no candidato)")
    parser.add_argument("--xgoog", default=None, help="Valor de x-goog-authuser (se ausente)")
    parser.add_argument("--out-headers", default=".cache/ytmusic_headers_merged.txt")
    parser.add_argument("--out-json", default=".cache/headers_auth.json")
    parser.add_argument("--attempt-setup", action="store_true", help="Tentar chamar ytmusicapi.setup com os headers montados")
    args = parser.parse_args(argv)

    candidate_path = Path(args.candidate)
    if not candidate_path.exists():
        print(f"Candidate headers not found: {candidate_path}", file=sys.stderr)
        return 2

    headers = load_candidate(candidate_path)

    missing = []
    if "cookie" not in {k.lower() for k in headers.keys()}:
        missing.append("cookie")
    if "x-goog-authuser" not in {k.lower() for k in headers.keys()}:
        missing.append("x-goog-authuser")

    # Merge user-provided values if given
    if args.cookie:
        headers["cookie"] = args.cookie
        if "cookie" in missing:
            missing.remove("cookie")
    if args.xgoog:
        headers["x-goog-authuser"] = args.xgoog
        if "x-goog-authuser" in missing:
            missing.remove("x-goog-authuser")

    out_headers = Path(args.out_headers)
    out_headers.parent.mkdir(parents=True, exist_ok=True)
    lines = build_header_lines(headers)
    out_headers.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote merged headers to: {out_headers}")

    if missing:
        print("Missing required entries:", ", ".join(missing))
        print("Provide them via --cookie and --xgoog, or capture full headers with the Selenium helper.")
        # Do not attempt setup if required entries are missing
        return 3

    if args.attempt_setup:
        try:
            import importlib

            setup_mod = importlib.import_module("ytmusicapi.setup")
            try:
                setup_mod.setup(filepath=args.out_json, headers_raw="\n".join(lines))
                print("ytmusicapi.setup succeeded, wrote:", args.out_json)
                return 0
            except Exception as e:  # pragma: no cover - runtime
                print("ytmusicapi.setup failed:", e, file=sys.stderr)
                return 4
        except Exception as e:
            print("ytmusicapi.setup not available:", e, file=sys.stderr)
            return 5

    print("Merged headers are ready. Run with --attempt-setup to try ytmusicapi.setup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
