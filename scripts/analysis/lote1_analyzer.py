#!/usr/bin/env python3
"""
Analisador Eficiente de Lotes - Ollama Remoto (Homelab)
GPU0 (RTX 2060) + GPU1 (GTX 1050) → Análise paralela sem overhead local
"""

import asyncio
import json
import logging
import subprocess
import hashlib
from pathlib import Path
from typing import Optional
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações Ollama Remoto
OLLAMA_GPU0 = "http://192.168.15.2:11434"  # RTX 2060
OLLAMA_GPU1 = "http://192.168.15.2:11435"  # GTX 1050
OLLAMA_MODEL = "shared-coder"
BATCH_SIZE = 2  # 2 arquivos por vez (rede via curl é mais lenta)
CACHE_DIR = Path("/home/edenilson/shared-auto-dev/.ollama_cache")
CACHE_DIR.mkdir(exist_ok=True)


def get_cache_key(file_path: Path) -> str:
    """Gera chave de cache com hash do arquivo + tamanho."""
    stat = file_path.stat()
    key_str = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
    return hashlib.md5(key_str.encode()).hexdigest()


def get_cached_result(file_path: Path) -> Optional[dict]:
    """Retorna resultado em cache se disponível."""
    cache_key = get_cache_key(file_path)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except:
            return None
    return None


def save_cached_result(file_path: Path, result: dict) -> None:
    """Salva resultado em cache."""
    cache_key = get_cache_key(file_path)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    cache_file.write_text(json.dumps(result))


async def check_ollama_health(url: str, gpu_id: int) -> bool:
    """Verifica se Ollama está respondendo."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-m", "5", f"{url}/api/tags"],
            capture_output=True,
            timeout=10
        )
        available = result.returncode == 0
        status = "✓" if available else "✗"
        logger.info(f"[GPU{gpu_id}] {status} {url}")
        return available
    except Exception as e:
        logger.error(f"[GPU{gpu_id}] Erro ao verificar: {e}")
        return False


async def analyze_file_ollama(
    file_path: Path,
    gpu_url: str,
    gpu_id: int
) -> dict:
    """Analisa arquivo com Ollama remoto (otimizado)."""
    
    # Verificar cache
    cached = get_cached_result(file_path)
    if cached:
        logger.info(f"[GPU{gpu_id}] ⚡ CACHE {file_path.name}")
        return cached
    
    try:
        # Ler arquivo (estratégia: análise por padrões simples primeiro)
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')
        
        # Extrair referências SHARED por grep (RÁPIDO)
        shared_refs = []
        public_funcs = []
        
        for i, line in enumerate(lines, 1):
            if 'shared' in line.lower():
                shared_refs.append({"linha": i, "texto": line.strip()})
            if line.strip().startswith('def ') and not line.strip().startswith('def _'):
                func_name = line.split('(')[0].replace('def ', '')
                public_funcs.append(func_name)
        
        # Se muitas referências, usar Ollama para refatoração específica
        if shared_refs:
            # Prompt CURTO e DIRETO
            prompt = f"""Arquivo: {file_path.name}
Encontradas {len(shared_refs)} referências "shared".
Recomendações de refatoração:

{json.dumps(shared_refs[:5])}

Forneça 2-3 linhas de refatoração."""
            
            logger.info(f"[GPU{gpu_id}] Analisando {file_path.name}...")
            
            result = subprocess.run(
                [
                    "curl", "-s", "-m", "20", f"{gpu_url}/api/generate",
                    "-X", "POST",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps({
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.2
                    })
                ],
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                resp = json.loads(result.stdout)
                refactoring = resp.get("response", "").strip()
            else:
                refactoring = "Erro ao contactar Ollama"
        else:
            refactoring = "Sem referências SHARED encontradas"
        
        # Compilar resultado
        output = {
            "arquivo": file_path.name,
            "caminho": str(file_path),
            "gpu": gpu_id,
            "shared_referencias": len(shared_refs),
            "detalhes": shared_refs[:3],
            "funcoes_publicas": public_funcs,
            "refactoring": refactoring,
            "sucesso": True
        }
        
        # Cachear
        save_cached_result(file_path, output)
        logger.info(f"[GPU{gpu_id}] ✓ {file_path.name} ({len(shared_refs)} refs)")
        return output
        
    except Exception as e:
        logger.error(f"[GPU{gpu_id}] ✗ {file_path.name}: {e}")
        return {
            "arquivo": file_path.name,
            "caminho": str(file_path),
            "gpu": gpu_id,
            "sucesso": False,
            "erro": str(e)
        }


async def process_batch_parallel(
    files: list[Path],
    batch_num: int
) -> list[dict]:
    """Processa 2 arquivos em paralelo (GPU0 + GPU1)."""
    logger.info(f"\n[LOTE {batch_num}] Processando {len(files)} arquivo(s)...")
    
    tasks = []
    for i, file_path in enumerate(files):
        gpu_url = OLLAMA_GPU0 if i % 2 == 0 else OLLAMA_GPU1
        gpu_id = 0 if i % 2 == 0 else 1
        tasks.append(analyze_file_ollama(file_path, gpu_url, gpu_id))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]


async def main():
    """LOTE 1: btc_trading_agent + shared_tray_agent + specialized_agents."""
    
    logger.info("="*70)
    logger.info("LOTE 1 - ANÁLISE PARALELA (Ollama Remoto)")
    logger.info("="*70)
    
    # Health check
    gpu0_ok = await check_ollama_health(OLLAMA_GPU0, 0)
    gpu1_ok = await check_ollama_health(OLLAMA_GPU1, 1)
    
    if not (gpu0_ok or gpu1_ok):
        logger.error("❌ Nenhuma GPU Ollama acessível!")
        return None
    
    # Coletar arquivos
    components = {
        "btc_trading_agent": Path("/home/edenilson/shared-auto-dev/btc_trading_agent"),
        "shared_tray_agent": Path("/home/edenilson/shared-auto-dev/shared_tray_agent"),
    }
    
    all_files = []
    for comp_name, comp_path in components.items():
        if comp_path.exists():
            files = list(comp_path.glob("*.py"))  # Apenas raiz, não recursivo
            files = [f for f in files if "__pycache__" not in str(f)]
            logger.info(f"  {comp_name}: {len(files)} arquivos")
            all_files.extend(files)
    
    logger.info(f"\nTotal: {len(all_files)} arquivos")
    
    # Processar em batches pequenos
    all_results = []
    for batch_idx in range(0, len(all_files), BATCH_SIZE):
        batch = all_files[batch_idx:batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1
        
        results = await process_batch_parallel(batch, batch_num)
        all_results.extend(results)
        
        # Pausa entre batches
        if batch_idx + BATCH_SIZE < len(all_files):
            await asyncio.sleep(1)
    
    # Salvar resultados
    output_file = Path("/home/edenilson/shared-auto-dev/LOTE1_ANALISE.json")
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # Resumo
    logger.info("\n" + "="*70)
    logger.info(f"✅ ANÁLISE COMPLETA")
    logger.info(f"  Resultados: {output_file}")
    logger.info(f"  Total processado: {len(all_results)} arquivos")
    
    sucesso = sum(1 for r in all_results if r.get("sucesso"))
    shared_total = sum(r.get("shared_referencias", 0) for r in all_results if r.get("sucesso"))
    
    logger.info(f"  Sucesso: {sucesso}/{len(all_results)}")
    logger.info(f"  Referências SHARED encontradas: {shared_total}")
    logger.info("="*70)
    
    return output_file


if __name__ == "__main__":
    output = asyncio.run(main())
    if output:
        print(f"\n🎯 Análise salva: {output}")
