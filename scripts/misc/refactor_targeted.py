#!/usr/bin/env python3
"""
Aplicar refatoração direcionada nos arquivos com maior contagem de 'eddie'.
"""
from pathlib import Path
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

TOP_FILES = [
    'generate_final_report.py',
    'grafana/exporters/eddie_whatsapp_exporter.py',
    'refactor_lote1.py',
    'generate_report.py',
    'lote1_analyzer.py',
    'update_knowledge.py',
    'lotes3to10_robust.py',
    'lote_processor.py',
    'openwebui_tool_executor.py',
    'lotes3to10_processor.py',
    'check_diretor_status.py',
    'refactor_lote2.py',
    'openwebui_integration.py',
    'lote2_processor.py',
    'fix_diretor_model.py',
    'whatsapp_bot.py',
    'validate_eddie_central_gauges.py',
    'test_ai_training.py',
    'openwebui_director_function.py',
    'update_eddie_central_json_phase2.py',
    'setup_google_calendar.py',
    'extract_whatsapp_train.py',
    'dashboard/control_panel.py',
    'dashboard/config.py',
    'validate_eddie_central_api.py',
    'configure_diretor_model.py',
    'tools/proxy_tool_interceptor.py',
    'telegram_bot.py',
    'specialized_agents/opensearch_agent.py',
]

REPLACEMENTS = [
    (r'\bEDDIE\b', 'SHARED'),
    (r'\beddie\b', 'shared'),
    (r"\bEddie\b", 'Shared'),
    (r'eddie_', 'shared_'),
]


def process_file(path: Path):
    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f'Skipping {path}: {e}')
        return False
    orig = content
    for pat, rep in REPLACEMENTS:
        content = re.sub(pat, rep, content)
    if content != orig:
        path.write_text(content, encoding='utf-8')
        logger.info(f'Modified {path}')
        return True
    return False


def main():
    base = Path('/home/edenilson/eddie-auto-dev')
    modified = []
    for f in TOP_FILES:
        p = base / f
        if p.exists():
            if process_file(p):
                modified.append(str(p))
        else:
            logger.debug(f'Not found: {p}')
    if modified:
        Path('/tmp/changed_targeted.txt').write_text('\n'.join(modified))
    logger.info(f'Done targeted refactor. Modified {len(modified)} files.')


if __name__ == '__main__':
    main()
