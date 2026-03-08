#!/usr/bin/env python3
"""
Refatoração Automática LOTE 8 - Scripts e Deploy
"""

import re
from pathlib import Path
from typing import Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

REPLACEMENTS = [
    (r'\beddie\b', 'shared'),
    (r'EDDIE', 'SHARED'),
    (r'eddie_', 'shared_'),
    (r'Eddie', 'Shared'),
]


def refactor_file(file_path: Path) -> Tuple[bool, str]:
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        for pat, rep in REPLACEMENTS:
            content = re.sub(pat, rep, content)
        if content != original:
            file_path.write_text(content, encoding='utf-8')
            changes = len(re.findall(r'shared_|SHARED|shared', content)) - len(re.findall(r'shared_|SHARED|shared', original))
            return True, f"✓ {changes} mudanças"
        return False, 'sem mudanças'
    except Exception as e:
        return False, f'✗ Erro: {e}'


def main():
    base = Path('/home/edenilson/eddie-auto-dev')
    targets = [base / 'scripts', base / 'deploy']
    total = 0
    modified = 0
    for t in targets:
        if not t.exists():
            logger.warning(f'Não encontrado: {t}')
            continue
        logger.info(f'Processando {t}')
        for p in t.rglob('*.py'):
            total += 1
            ok, msg = refactor_file(p)
            if ok:
                modified += 1
                logger.info(f'  {p.relative_to(base)}: {msg}')
    logger.info(f'Arquivos processados: {total} modificados: {modified}')


if __name__ == '__main__':
    main()
