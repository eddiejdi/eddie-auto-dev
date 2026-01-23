#!/usr/bin/env python3
"""
Replace occurrences of localhost:8501 in markdown/html/text files with a public URL.

Usage:
  tools/set_interceptor_url.py --url https://my-tunnel.example.com
  or set INTERCEPTOR_PUBLIC_URL env var and run without --apply to preview.

By default the script only previews changes. Pass --apply to modify files.
"""
import os
import re
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATTERNS = [r"http://localhost:8501", r"http://127\.0\.0\.1:8501", r"localhost:8501"]
EXCLUDE = ['.venv', '.venv_github_agent', '.venv_validator', 'node_modules']


def files_to_patch(root: Path):
    for p in root.rglob('*'):
        if any(part in EXCLUDE for part in p.parts):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() in ('.md', '.html', '.txt', '.py', '.sh', '.json'):
            yield p


def preview_and_apply(url: str, apply: bool = False):
    regex = re.compile('|'.join(DEFAULT_PATTERNS))
    changed = []
    for f in files_to_patch(ROOT):
        try:
            text = f.read_text(encoding='utf-8')
        except Exception:
            continue
        if regex.search(text):
            new = regex.sub(url, text)
            changed.append((f, text, new))

    if not changed:
        print('No files would be changed.')
        return 0

    print(f'Found {len(changed)} files with localhost:8501 references:')
    for f, old, new in changed:
        print(' -', f)

    if not apply:
        print('\nRun with --apply to write changes.')
        return 0

    for f, old, new in changed:
        f.write_text(new, encoding='utf-8')
        print('Patched', f)

    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', help='Public URL to replace localhost:8501 with')
    ap.add_argument('--apply', action='store_true', help='Apply changes')
    args = ap.parse_args()

    url = args.url or os.environ.get('INTERCEPTOR_PUBLIC_URL')
    if not url:
        print('Provide --url or set INTERCEPTOR_PUBLIC_URL env var')
        return 2

    return preview_and_apply(url, apply=args.apply)


if __name__ == '__main__':
    raise SystemExit(main())
