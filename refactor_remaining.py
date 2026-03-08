#!/usr/bin/env python3
"""
Refatoração em lote para componentes restantes (LOTE 3-5, LOTE 4)
"""

import re
from pathlib import Path
from typing import Tuple, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

REPLACEMENTS = [
    (r'\bshared_trading\b', 'crypto_trading'),
    (r'\bshared_tray\b', 'system_tray'),
    (r'shared_', 'shared_'),
    (r'SHARED', 'SHARED'),
    (r'Shared', 'Shared'),
]


def refactor_file(file_path: Path) -> Tuple[bool, str]:
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        for pat, rep in REPLACEMENTS:
            content = re.sub(pat, rep, content)
        if content != original:
            file_path.write_text(content, encoding='utf-8')
            changes = len(re.findall(r'shared_|crypto|SHARED|CRYPTO', content)) - len(re.findall(r'shared_|crypto|SHARED|CRYPTO', original))
            return True, f"✓ {changes} mudanças"
        return False, 'sem mudanças'
    except Exception as e:
        return False, f'✗ Erro: {e}'


def process_dirs(dirs: List[Path]) -> None:
    base = Path('/home/edenilson/shared-auto-dev')
    total = 0
    modified = 0
    for d in dirs:
        if not d.exists():
            logger.info(f'Skipping missing: {d}')
            continue
        logger.info(f'Processing {d}')
        for p in d.rglob('*.py'):
            total += 1
            ok, msg = refactor_file(p)
            if ok:
                modified += 1
                logger.info(f'  {p.relative_to(base)}: {msg}')
    logger.info(f'Processed {total} files, modified {modified}')


if __name__ == '__main__':
    base = Path('/home/edenilson/shared-auto-dev')
    dirs = [
        base / 'home_assistant',
        base / 'homeassistant',
        base / 'home_assistant_integration',
        base / 'estou-aqui',
        base / 'github-mcp-server',
        base / 'rag-mcp-server',
    ]
    process_dirs(dirs)
