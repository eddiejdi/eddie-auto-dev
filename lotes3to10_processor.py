#!/usr/bin/env python3
"""
Processador Massivo - LOTES 3-10 em Paralelo
Processa estou-aqui, smartlife_integration, etc.
"""

import asyncio
import json
import logging
import subprocess
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

# Mapeamento de componentes per lote
LOTES = {
    3: ["estou-aqui"],
    4: ["smartlife_integration", "homeassistant_integration"],
    5: ["rag-mcp-server", "github-mcp-server"],
    6: ["shared-copilot/src"],
    7: ["tools"],
    8: ["scripts", "deploy"],
    9: ["agent_data", "training_data"],
    10: ["solutions", "dev_projects"]
}

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
        logger.info(f"[GPU{gpu_id}] ✓ {file_path.name} ({result['shared_count']} refs)")
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

async def process_lote(lote_num, files: list[Path]) -> dict:
    logger.info(f"\n{'='*70}")
    logger.info(f"LOTE {lote_num}: {len(files)} arquivo(s)")
    logger.info(f"{'='*70}")
    
    results = []
    tasks = []
    for i, file_path in enumerate(files):
        gpu_url = OLLAMA_GPU0 if i % 2 == 0 else OLLAMA_GPU1
        gpu_id = 0 if i % 2 == 0 else 1
        tasks.append(analyze_file(file_path, gpu_url, gpu_id))
    
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for r in batch_results:
        if not isinstance(r, Exception):
            results.append(r)
    
    # Salvar com nome que suporte formato de string
    lote_file = RESULTS_DIR / f"lote_{str(lote_num)}.json"
    with open(lote_file, "w") as f:
        json.dump(results, f, indent=2)
    
    sucesso = sum(1 for r in results if r.get("sucesso"))
    shared_total = sum(r.get("shared_count", 0) for r in results)
    
    logger.info(f"📊 {sucesso}/{len(results)} | SHARED: {shared_total}")
    
    return {
        "lote": lote_num,
        "total": len(results),
        "sucesso": sucesso,
        "shared_total": shared_total
    }

async def main():
    """Processar LOTES 3-10."""
    
    base_path = Path("/home/edenilson/shared-auto-dev")
    all_summaries = []
    
    for lote_num, components in LOTES.items():
        files = []
        
        for comp in components:
            comp_path = base_path / comp
            if comp_path.exists():
                py_files = [f for f in comp_path.glob("**/*.py") if "__pycache__" not in str(f)]
                logger.info(f"  {comp}: {len(py_files)} arquivos")
                files.extend(py_files)
        
        if not files:
            logger.warning(f"LOTE {lote_num}: nenhum arquivo encontrado")
            continue
        
        logger.info(f"LOTE {lote_num} Total: {len(files)}")
        
        # Processar em batches de 5
        lote_summaries = []
        for batch_idx in range(0, len(files), 5):
            batch = files[batch_idx:batch_idx+5]
            batch_num = batch_idx // 5 + 1
            
            batch_summary = await process_lote(f"{lote_num}.{batch_num}", batch)
            lote_summaries.append(batch_summary)
            
            if batch_idx + 5 < len(files):
                await asyncio.sleep(1)
        
        all_summaries.extend(lote_summaries)
    
    # Salvar resumo geral
    summary_file = RESULTS_DIR / "LOTES3-10_RESUMO.json"
    with open(summary_file, "w") as f:
        json.dump(all_summaries, f, indent=2)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ LOTES 3-10 COMPLETOS")
    logger.info(f"{'='*70}")
    return summary_file

if __name__ == "__main__":
    try:
        output = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido")
        sys.exit(130)
