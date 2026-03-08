#!/usr/bin/env python3
"""
Validador de Sintaxe Python - Verifica todos os arquivos do LOTE 1-2
"""

import py_compile
import json
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def validate_python_files(component_path: Path) -> dict:
    """Valida sintaxe de todos os arquivos Python."""
    
    results = {
        "componente": component_path.name,
        "total_arquivos": 0,
        "sucesso": 0,
        "erros": [],
        "avisos": []
    }
    
    for py_file in component_path.glob("*.py"):
        results["total_arquivos"] += 1
        
        try:
            py_compile.compile(str(py_file), doraise=True)
            results["sucesso"] += 1
            logger.info(f"✓ {py_file.name}")
        except py_compile.PyCompileError as e:
            error_msg = f"{py_file.name}: {e}"
            results["erros"].append(error_msg)
            logger.error(f"✗ {error_msg}")
    
    return results

def main():
    """Valida LOTE 1 e LOTE 2."""
    
    base_path = Path("/home/edenilson/eddie-auto-dev")
    
    components = [
        base_path / "btc_trading_agent",
        base_path / "eddie_tray_agent",
        base_path / "homelab_copilot_agent",
        base_path / "specialized_agents",
    ]
    
    all_results = []
    total_erros = 0
    
    for comp_path in components:
        if comp_path.exists():
            logger.info(f"\n{'='*70}")
            logger.info(f"Validando: {comp_path.name}")
            logger.info(f"{'='*70}")
            
            result = validate_python_files(comp_path)
            all_results.append(result)
            total_erros += len(result["erros"])
    
    # Salvar relatório
    output_file = Path("/home/edenilson/eddie-auto-dev/analysis_results/VALIDACAO_SINTAXE.json")
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Resumo
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ VALIDAÇÃO COMPLETA")
    logger.info(f"{'='*70}")
    
    total_arquivos = sum(r["total_arquivos"] for r in all_results)
    total_sucesso = sum(r["sucesso"] for r in all_results)
    
    logger.info(f"Total de arquivos: {total_arquivos}")
    logger.info(f"Validados com sucesso: {total_sucesso}/{total_arquivos}")
    logger.info(f"Erros encontrados: {total_erros}")
    logger.info(f"Relatório: {output_file}")
    
    if total_erros == 0:
        logger.info("✨ Todo código está sintaticamente correto!")
    else:
        logger.warning(f"⚠️  {total_erros} erros encontrados - verifique relatório")

if __name__ == "__main__":
    main()
