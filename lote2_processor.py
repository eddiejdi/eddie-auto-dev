#!/usr/bin/env python3
"""
Processador LOTE 2 - Homelab Copilot Agent + Specialized Agents
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
CACHE_DIR = Path("/home/edenilson/eddie-auto-dev/.analysis_cache")
RESULTS_DIR = Path("/home/edenilson/eddie-auto-dev/analysis_results")
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
        
        eddie_refs = []
        imports = []
        public_funcs = []
        
        for i, line in enumerate(lines, 1):
            if 'eddie' in line.lower():
                eddie_refs.append((i, line.strip()))
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                imports.append(line.strip())
            if line.strip().startswith('def ') and not line.strip().startswith('def _'):
                func_name = line.split('(')[0].replace('def ', '').strip()
                public_funcs.append(func_name)
        
        result = {
            "arquivo": file_path.name,
            "caminho": str(file_path.relative_to(Path.home())),
            "gpu": gpu_id,
            "eddie_count": len(eddie_refs),
            "eddie_linhas": eddie_refs[:5],
            "imports_count": len(imports),
            "funcoes_publicas": public_funcs[:5],
            "linhas_total": len(lines),
            "sucesso": True
        }
        
        save_cached(file_path, result)
        logger.info(f"[GPU{gpu_id}] ✓ {file_path.name} ({result['eddie_count']} refs)")
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

async def process_lote(lote_num: int, files: list[Path]) -> dict:
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
    
    lote_file = RESULTS_DIR / f"lote_{lote_num:02d}.json"
    with open(lote_file, "w") as f:
        json.dump(results, f, indent=2)
    
    sucesso = sum(1 for r in results if r.get("sucesso"))
    eddie_total = sum(r.get("eddie_count", 0) for r in results)
    
    logger.info(f"📊 Lote {lote_num}: {sucesso}/{len(results)} | EDDIE: {eddie_total}")
    
    return {
        "lote": lote_num,
        "arquivo": str(lote_file),
        "total": len(results),
        "sucesso": sucesso,
        "eddie_total": eddie_total
    }

async def main():
    """LOTE 2: homelab_copilot_agent + specialized_agents."""
    
    base_path = Path("/home/edenilson/eddie-auto-dev")
    files = []
    
    # homelab_copilot_agent
    homelab_path = base_path / "homelab_copilot_agent"
    if homelab_path.exists():
        py_files = [f for f in homelab_path.glob("*.py") if "__pycache__" not in str(f)]
        logger.info(f"homelab_copilot_agent: {len(py_files)} arquivos")
        files.extend(py_files)
    
    # specialized_agents (apenas raiz)
    spec_path = base_path / "specialized_agents"
    if spec_path.exists():
        py_files = [f for f in spec_path.glob("*.py") if "__pycache__" not in str(f)]
        logger.info(f"specialized_agents: {len(py_files)} arquivos")
        files.extend(py_files)
    
    logger.info(f"Total LOTE 2: {len(files)} arquivos\n")
    
    # Processar em batches de 3
    all_summary = []
    for batch_idx in range(0, len(files), 3):
        batch = files[batch_idx:batch_idx+3]
        batch_num = batch_idx // 3 + 1
        
        lote_summary = await process_lote(batch_num, batch)
        all_summary.append(lote_summary)
        
        if batch_idx + 3 < len(files):
            await asyncio.sleep(1)
    
    summary_file = RESULTS_DIR / "LOTE2_RESUMO.json"
    with open(summary_file, "w") as f:
        json.dump(all_summary, f, indent=2)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ LOTE 2 COMPLETO → {summary_file}")
    logger.info(f"{'='*70}")
    return summary_file

if __name__ == "__main__":
    try:
        output = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido (resultados parciais salvos)")
        sys.exit(130)
