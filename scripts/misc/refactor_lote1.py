#!/usr/bin/env python3
"""
Refatoração Automática LOTE 1 - Trading Bot
Remove refs SHARED, renomeia para CRYPTO
"""

import re
from pathlib import Path
from typing import Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Mapeamentos de refatoração
REPLACEMENTS = [
    # Variáveis e funções
    (r'\bshared_trading\b', 'crypto_trading'),
    (r'\bshared_tray\b', 'system_tray'),
    (r'\bshared_agent\b', 'trading_agent'),
    (r'shared_config', 'crypto_config'),
    (r'shared_logger', 'crypto_logger'),
    (r'shared_cache', 'crypto_cache'),
    (r'shared_db', 'crypto_db'),
    
    # Import paths
    (r'from btc_trading_agent\.shared', 'from crypto_trading_bot'),
    (r'from shared_tray_agent', 'from system_tray_agent'),
    (r'import shared_', 'import crypto_'),
    
    # Environment variables e configs
    (r'EDDIE_API_KEY', 'CRYPTO_API_KEY'),
    (r'EDDIE_HOME', 'CRYPTO_HOME'),
    (r'EDDIE_MODE', 'CRYPTO_MODE'),
    (r'EDDIE_LOG_LEVEL', 'CRYPTO_LOG_LEVEL'),
    (r'EDDIE_DB_', 'CRYPTO_DB_'),
    
    # Strings em logs
    (r'"shared', '"crypto'),
    (r"'shared", "'crypto"),
    (r'SHARED', 'CRYPTO'),
    (r'Shared', 'Crypto'),
]

def refactor_file(file_path: Path) -> Tuple[bool, str]:
    """Refatora um arquivo Python."""
    
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Aplicar substituições (case-sensitive primeiro)
        for pattern, replacement in REPLACEMENTS:
            content = re.sub(pattern, replacement, content)
        
        # Se houve mudanças, escrever de volta
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            
            # Contar mudanças
            changes_count = len(re.findall(r'crypto', content)) - len(re.findall(r'crypto', original_content))
            return True, f"✓ {changes_count} mudanças"
        else:
            return False, "sem mudanças"
            
    except Exception as e:
        return False, f"✗ Erro: {e}"

def main():
    """Refatora LOTE 1 completo."""
    
    base_path = Path("/home/edenilson/shared-auto-dev")
    components = [
        base_path / "btc_trading_agent",
        base_path / "shared_tray_agent",
    ]
    
    logger.info("="*70)
    logger.info("REFATORAÇÃO AUTOMÁTICA - LOTE 1")
    logger.info("="*70)
    
    total_files = 0
    modified_files = 0
    total_changes = 0
    
    for comp_path in components:
        if not comp_path.exists():
            logger.warning(f"Componente não encontrado: {comp_path}")
            continue
        
        logger.info(f"\n{comp_path.name}:")
        
        py_files = [f for f in comp_path.glob("*.py") if "__pycache__" not in str(f)]
        
        for py_file in py_files:
            total_files += 1
            success, message = refactor_file(py_file)
            
            if success:
                modified_files += 1
                logger.info(f"  {py_file.name}: {message}")
            else:
                logger.debug(f"  {py_file.name}: {message}")
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ REFATORAÇÃO CONCLUÍDA")
    logger.info(f"{'='*70}")
    logger.info(f"Arquivos processados: {total_files}")
    logger.info(f"Arquivos modificados: {modified_files}")
    logger.info(f"Taxa de mudança: {modified_files/total_files*100:.1f}%")
    
    # Próximos passos
    logger.info(f"\n⚠️  PRÓXIMOS PASSOS:")
    logger.info(f"1. Validar sintaxe: python -m py_compile btc_trading_agent/*.py")
    logger.info(f"2. Executar testes: pytest tests/unit/trading_bot/")
    logger.info(f"3. Verificar imports: python -c 'import btc_trading_agent'")

if __name__ == "__main__":
    main()
