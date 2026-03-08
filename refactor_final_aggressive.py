#!/usr/bin/env python3
"""
Refactor final e agressivo: remove todas as ocorrências restantes de 'eddie'/'EDDIE'
Preserva imports e contextos importantes.
"""
import os
import re
import sys
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def safe_replacements() -> list[tuple[str, str]]:
    """Padrões de substituição seguros."""
    return [
        # Comments and docstrings about eddie/EDDIE
        (r'\b[Ee]ddie\b(?=\s*(agent|bot|system|service|component))', 'Crypto'),
        (r'\b[Ee]ddie\b(?=\s*(tray|ui|interface))', 'System'),
        (r'\b[Ee]ddie\b(?=\s*(assistant|helper|tool))', 'Shared'),
        (r'\bEDDIE\b(?=\s*(API|AGENT|SERVER|SERVICE|COMPONENT))', 'CRYPTO'),
        
        # Variable and function names
        (r'eddie_', 'crypto_'),
        (r'EDDIE_', 'CRYPTO_'),
        
        # Module/package names (safe in strings and paths)
        (r'eddie_tray_agent', 'system_tray_agent'),
        (r'eddie_coder', 'shared_coder'),
        (r'eddie_assistant', 'shared_assistant'),
        
        # Path references
        (r'eddie-auto-dev', 'crypto-auto-dev'),
        (r'/eddie/', '/crypto/'),
        
        # Remaining standalone cases
        (r'\bEddie\b', 'Crypto'),
        (r'\beddie\b', 'crypto'),
    ]

def refactor_file(filepath: Path) -> bool:
    """
    Refactor um arquivo com substituições seguras.
    Retorna True se arquivo foi modificado.
    """
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        original = content
        
        for pattern, replacement in safe_replacements():
            content = re.sub(pattern, replacement, content)
        
        if content != original:
            filepath.write_text(content, encoding='utf-8')
            logger.info(f"Modified {filepath.relative_to(Path.cwd())}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error processing {filepath}: {e}")
        return False

def main():
    """Refactor all Python files in the repository."""
    repo_root = Path.cwd()
    
    # Ignorar diretórios
    ignore_dirs = {
        '.git', '.venv', '__pycache__', '.pytest_cache',
        '.analysis_cache', '.ollama_cache', 'node_modules',
        '.vscode', '.idea', '.DS_Store'
    }
    
    modified_count = 0
    total_count = 0
    
    for py_file in sorted(repo_root.rglob('*.py')):
        # Skip ignored paths
        if any(part in ignore_dirs for part in py_file.parts):
            continue
        
        total_count += 1
        if refactor_file(py_file):
            modified_count += 1
    
    logger.info(f"✓ Refactored {modified_count}/{total_count} Python files")
    
    # Também refatorar alguns arquivo de config/docs que podem conter referências
    for ext in ['.md', '.yml', '.yaml', '.sh', '.json']:
        for config_file in sorted(repo_root.rglob(f'*{ext}')):
            if any(part in ignore_dirs for part in config_file.parts):
                continue
            if refactor_file(config_file):
                modified_count += 1
    
    logger.info(f"✓ Total files refactored: {modified_count}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
