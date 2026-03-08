#!/usr/bin/env python3
"""
Processador Robustofor LOTES 3-10
Componentes: estou-aqui, integrations, mcp-servers, tools, scripts, misc
"""

import asyncio
import json
import logging
import hashlib
from pathlib import Path
from typing import Optional
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

OLLAMA_GPU0 = "http://192.168.15.2:11434"
OLLAMA_GPU1 = "http://192.168.15.2:11435"
CACHE_DIR = Path("/home/edenilson/shared-auto-dev/.analysis_cache")
RESULTS_DIR = Path("/home/edenilson/shared-auto-dev/analysis_results")
CACHE_DIR.mkdir(exist_ok=True)

def get_cache_key(file_path: Path) -> str:
    stat = file_path.stat()
    key_str = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
    return hashlib.md5(key_str.encode()).hexdigest()

def load_cached(file_path: Path) -> Optional[dict]:
    cache_file = CACHE_DIR / f"{get_cache_key(file_path)}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except:
            return None
    return None

def save_cached(file_path: Path, result: dict) -> None:
    cache_file = CACHE_DIR / f"{get_cache_key(file_path)}.json"
    cache_file.write_text(json.dumps(result))

async def analyze_file(file_path: Path, gpu_url: str, gpu_id: int) -> dict:
    cached = load_cached(file_path)
    if cached:
        return cached
    
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')
        
        shared_refs = []
        imports = []
        public_funcs = []
        
        for i, line in enumerate(lines, 1):
            if 'shared' in line.lower():
                shared_refs.append((i, line.strip()))
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                imports.append(line.strip())
            if line.strip().startswith('def ') and not line.strip().startswith('def _'):
                func_name = line.split('(')[0].replace('def ', '').strip()
                public_funcs.append(func_name)
        
        result = {
            "arquivo": file_path.name,
            "caminho": str(file_path.relative_to(Path.home())),
            "gpu": gpu_id,
            "shared_count": len(shared_refs),
            "shared_linhas": shared_refs[:3],
            "imports_count": len(imports),
            "funcoes_publicas": public_funcs[:5],
            "linhas_total": len(lines),
            "sucesso": True
        }
        
        save_cached(file_path, result)
        logger.info(f"[GPU{gpu_id}] ✓ {file_path.name}")
        return result
        
    except Exception as e:
        logger.error(f"[GPU{gpu_id}] ✗ {file_path.name}: {e}")
        return {
            "arquivo": file_path.name,
            "caminho": str(file_path),
            "gpu": gpu_id,
            "sucesso": False,
            "erro": str(e)
        }

async def process_component(comp_name: str, comp_path: Path, output_prefix: str) -> dict:
    """Processa um componente completo."""
    
    if not comp_path.exists():
        logger.warning(f"Componente não encontrado: {comp_path}")
        return {"componente": comp_name, "total": 0, "shared_refs": 0}
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Componente: {comp_name}")
    logger.info(f"{'='*70}")
    
    # Coletar todos os arquivos (.py apenas)
    all_files = []
    for py_file in comp_path.rglob("*.py"):
        if "__pycache__" not in str(py_file):
            all_files.append(py_file)
    
    logger.info(f"Total de arquivos: {len(all_files)}")
    
    # Processar em batches de 10
    all_results = []
    for batch_idx in range(0, len(all_files), 10):
        batch = all_files[batch_idx:batch_idx+10]
        batch_num = batch_idx // 10 + 1
        
        tasks = []
        for i, file_path in enumerate(batch):
            gpu_url = OLLAMA_GPU0 if i % 2 == 0 else OLLAMA_GPU1
            gpu_id = 0 if i % 2 == 0 else 1
            tasks.append(analyze_file(file_path, gpu_url, gpu_id))
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in batch_results:
            if not isinstance(r, Exception):
                all_results.append(r)
        
        sucesso = sum(1 for r in all_results if r.get("sucesso"))
        shared_total = sum(r.get("shared_count", 0) for r in all_results)
        
        logger.info(f"  Batch {batch_num}: {sucesso}/{len(all_results)} | SHARED: {shared_total}")
        
        if batch_idx + 10 < len(all_files):
            await asyncio.sleep(1)
    
    # Salvar resultados
    output_file = RESULTS_DIR / f"{output_prefix}.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    sucesso = sum(1 for r in all_results if r.get("sucesso"))
    shared_total = sum(r.get("shared_count", 0) for r in all_results)
    
    logger.info(f"✅ {comp_name}: {len(all_results)} arquivos, {shared_total} refs SHARED")
    
    return {
        "componente": comp_name,
        "arquivo": str(output_file),
        "total": len(all_results),
        "sucesso": sucesso,
        "shared_refs": shared_total
    }

async def main():
    """Processa LOTES 3-10."""
    
    base_path = Path("/home/edenilson/shared-auto-dev")
    
    components = {
        "LOTE3_estou-aqui": base_path / "estou-aqui",
        "LOTE4_smartlife": base_path / "smartlife_integration",
        "LOTE4_homeassistant": base_path / "homeassistant_integration",
        "LOTE5_rag-mcp": base_path / "rag-mcp-server",
        "LOTE5_github-mcp": base_path / "github-mcp-server",
        "LOTE6_copilot": base_path / "shared-copilot" / "src",
        "LOTE7_tools": base_path / "tools",
        "LOTE8_scripts": base_path / "scripts",
        "LOTE8_deploy": base_path / "deploy",
    }
    
    all_summaries = []
    
    for output_name, comp_path in components.items():
        summary = await process_component(
            comp_path.name,
            comp_path,
            output_name
        )
        all_summaries.append(summary)
    
    # Salvar resumo geral
    summary_file = RESULTS_DIR / "LOTES3-10_RESUMO.json"
    with open(summary_file, "w") as f:
        json.dump(all_summaries, f, indent=2)
    
    # Estatísticas finais
    total_arquivos = sum(s["total"] for s in all_summaries)
    total_eddie = sum(s["shared_refs"] for s in all_summaries)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ LOTES 3-10 COMPLETOS")
    logger.info(f"{'='*70}")
    logger.info(f"Total de arquivos: {total_arquivos}")
    logger.info(f"Referências SHARED: {total_eddie}")
    logger.info(f"Resumo: {summary_file}")
    logger.info(f"{'='*70}")
    
    return summary_file

if __name__ == "__main__":
    try:
        output = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido (resultados parciais salvos)")
        sys.exit(130)
