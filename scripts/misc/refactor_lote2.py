#!/usr/bin/env python3
"""
Refatoração Automática LOTE 2 - Homelab + Specialized Agents
"""

import re
from pathlib import Path
from typing import Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

REPLACEMENTS = [
    (r'\bshared_trading\b', 'crypto_trading'),
    (r'\bshared_tray\b', 'system_tray'),
    (r'\bshared_agent\b', 'agent'),
    (r'shared_config', 'homelab_config'),
    (r'shared_logger', 'homelab_logger'),
    (r'shared_cache', 'homelab_cache'),
    (r'shared_db', 'homelab_db'),
    (r'from shared_tray_agent', 'from system_tray_agent'),
    (r'import shared_', 'import homelab_'),
    (r'EDDIE_API_KEY', 'HOMELAB_API_KEY'),
    (r'SHARED', 'HOMELAB'),
]


def refactor_file(file_path: Path) -> Tuple[bool, str]:
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        for pat, rep in REPLACEMENTS:
            content = re.sub(pat, rep, content)
        if content != original:
            file_path.write_text(content, encoding='utf-8')
            changes = len(re.findall(r'HOMELAB|homelab_|homelab', content)) - len(re.findall(r'HOMELAB|homelab_|homelab', original))
            return True, f"✓ {changes} mudanças"
        return False, 'sem mudanças'
    except Exception as e:
        return False, f'✗ Erro: {e}'


def main():
    base = Path('/home/edenilson/shared-auto-dev')
    targets = [base / 'homelab_copilot_agent', base / 'specialized_agents']

    logger.info('REFATORAÇÃO LOTE 2 - Homelab + specialized_agents')
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
