#!/usr/bin/env python3
"""
Refatoração em todos os arquivos rastreados pelo git (extensões seguras).
Usa `git ls-files` para evitar tocar arquivos ignorados/untracked.
"""
from pathlib import Path
import subprocess
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

EXTS = ('.py', '.md', '.json', '.yml', '.yaml', '.sh', '.txt')
REPLACEMENTS = [
    (r'\bEDDIE\b', 'SHARED'),
    (r'\beddie\b', 'shared'),
    (r"\bEddie\b", 'Shared'),
    (r'eddie_', 'shared_'),
]


def git_tracked_files():
    output = subprocess.check_output(['git', 'ls-files'], text=True)
    return [Path(p) for p in output.splitlines()]


def process_file(p: Path):
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        return False
    orig = text
    for pat, rep in REPLACEMENTS:
        text = re.sub(pat, rep, text)
    if text != orig:
        p.write_text(text, encoding='utf-8')
        logger.info(f'Modified {p}')
        return True
    return False


def main():
    files = git_tracked_files()
    modified = []
    for f in files:
        if f.suffix.lower() in EXTS:
            if process_file(f):
                modified.append(str(f))
    if modified:
        Path('/tmp/changed_tracked.txt').write_text('\n'.join(modified))
    logger.info(f'Done. Modified {len(modified)} tracked files.')


if __name__ == '__main__':
    main()
