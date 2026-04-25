#!/usr/bin/env python3
"""Reconciliar `Curtidas` no YouTube Music via Playwright.

Este utilitário tenta adicionar lotes de vídeos (IDs) a uma playlist pública
usando Playwright. O script foi feito para ser tolerante a ambientes onde
Playwright não esteja disponível ou onde a rede esteja bloqueada — nesses
casos ele grava um `content.txt` de *dry-run* na pasta de sessão para
registro e inspeção posterior.

Uso (exemplo):
  python tools/reconcile_ytmusic_playwright.py --batch-size 10

Regras:
- Sempre grava um diretório `call_<timestamp>_auto` dentro da sessão para
  manter compatibilidade com o parser existente (`parse_playwright_add_loop_results.py`).

Docstrings em PT-BR. Tipos e validações básicos.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Optional
import json
import time
import argparse
import logging
import sys

LOG = logging.getLogger("reconcile_ytmusic")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def chunk_videoids(videoids: List[str], start: int, batch_size: int) -> List[str]:
    """Retorna um slice com os próximos `batch_size` ids a partir de `start`.

    Args:
        videoids: lista completa de IDs (strings de 11 chars típicos do YouTube).
        start: índice inicial (0-based).
        batch_size: tamanho do lote.

    Returns:
        Lista de IDs para processar neste lote.
    """
    if start < 0:
        raise ValueError("start must be >= 0")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    return videoids[start : start + batch_size]


def write_call_dryrun(session_dir: Path, batch: List[str], note: str) -> Path:
    """Grava um diretório `call_*` com um `content.txt` descrevendo ações.

    Retorna o caminho do `call` criado.
    """
    ts = int(time.time())
    call_dir = session_dir / f"call_auto_{ts}"
    call_dir.mkdir(parents=True, exist_ok=True)
    content = {
        "type": "dry-run",
        "timestamp": ts,
        "note": note,
        "videos": batch,
    }
    (call_dir / "content.txt").write_text(json.dumps(content, indent=2))
    LOG.info("Wrote dry-run call to %s", call_dir)
    return call_dir


def run_playwright_batch(
    batch: List[str],
    playlist_name: str,
    storage_state: Optional[Path],
    headless: bool,
    max_retries: int,
    session_dir: Path,
) -> Dict[str, int]:
    """Tenta executar um lote via Playwright.

    Se Playwright não estiver disponível ou ocorrer erro de import, o método
    retorna sem exceção e grava um dry-run para inspeção.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # pragma: no cover - depende do ambiente
        LOG.warning("Playwright not available: %s", e)
        call = write_call_dryrun(session_dir, batch, note="playwright-not-available")
        return {"planned": len(batch), "succeeded": 0, "failed": len(batch), "call_dir": str(call)}

    result = {"planned": len(batch), "succeeded": 0, "failed": 0}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context_kwargs = {}
        if storage_state and storage_state.exists():
            context_kwargs["storage_state"] = str(storage_state)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        for vid in batch:
            url = f"https://music.youtube.com/watch?v={vid}"
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    LOG.info("Navigating to %s (attempt %d)", url, attempt)
                    page.goto(url, timeout=60000)
                    # Tenta clicar no botão de salvar/Save. Heurísticas tolerantes:
                    try:
                        # seletor por aria-label parcial
                        locator = page.locator("button[aria-label*=Save]")
                        if locator.count() > 0:
                            locator.first.click()
                        else:
                            # alternativa: texto 'Save'
                            if page.get_by_text("Save").count() > 0:
                                page.get_by_text("Save").first.click()
                            elif page.get_by_text("Salvar").count() > 0:
                                page.get_by_text("Salvar").first.click()
                    except Exception as e:
                        LOG.debug("Save click attempt failed: %s", e)

                    # Seleciona a playlist pelo nome quando o overlay aparecer
                    try:
                        if page.get_by_text(playlist_name).count() > 0:
                            page.get_by_text(playlist_name).first.click()
                        else:
                            # aguarda um pouco para overlay renderizar
                            page.wait_for_timeout(1000)
                            if page.get_by_text(playlist_name).count() > 0:
                                page.get_by_text(playlist_name).first.click()
                    except Exception:
                        LOG.debug("Playlist selection not found yet for %s", vid)

                    # heurística final: busca por texto de confirmação
                    page.wait_for_timeout(800)
                    content = page.content()
                    if "Added to" in content or "Adicionado" in content or playlist_name in content:
                        success = True
                        LOG.info("Marked video %s as added (heuristic)", vid)
                        break
                except Exception as e:
                    LOG.warning("Attempt %d failed for %s: %s", attempt, vid, e)
                    page.wait_for_timeout(500 * attempt)

            if success:
                result["succeeded"] += 1
            else:
                result["failed"] += 1

        # grava um resumo no diretório de sessão
        note = {"result": result, "playlist": playlist_name, "videos": batch}
        call_dir = write_call_dryrun(session_dir, batch, note=json.dumps(note))
        # fecha
        context.close()
        browser.close()

    result["call_dir"] = str(call_dir)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcilia Curtidas -> playlist pública via Playwright")
    parser.add_argument("--videoids", default=".cache/ytmusic_videoids.json", help="Arquivo JSON com lista de video IDs")
    parser.add_argument("--batch-size", type=int, default=10, help="Número de vídeos por lote")
    parser.add_argument("--start", type=int, default=0, help="Índice inicial no arquivo de videoids")
    parser.add_argument("--playlist-name", type=str, default="Curtidas - Pública (reordenado)", help="Nome da playlist alvo")
    parser.add_argument("--session-dir", type=Path, default=Path.home() / ".config/Code/User/workspaceStorage/76f8845b0ed394e778733b67669998cb/GitHub.copilot-chat/chat-session-resources/3788fc31-6d1b-4216-9109-97df3d7ef256", help="Pasta de sessão para gravar call_*/content.txt")
    parser.add_argument("--storage-state", type=Path, default=None, help="Playwright storage_state json para sessão autenticada")
    parser.add_argument("--headless", action="store_true", help="Executar headless (padrão: False)")
    parser.add_argument("--max-retries", type=int, default=3, help="Tentativas por item")
    parser.add_argument("--dry-run", action="store_true", help="Não executar Playwright; gravar apenas dry-run")

    args = parser.parse_args(argv)

    # carrega video ids
    vid_path = Path(args.videoids)
    if not vid_path.exists():
        LOG.error("videoids file not found: %s", vid_path)
        return 2
    videoids = json.loads(vid_path.read_text())
    batch = chunk_videoids(videoids, args.start, args.batch_size)

    session_dir: Path = args.session_dir
    session_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        call_dir = write_call_dryrun(session_dir, batch, note="manual dry-run")
        print(json.dumps({"planned": len(batch), "call_dir": str(call_dir)}))
        return 0

    result = run_playwright_batch(
        batch=batch,
        playlist_name=args.playlist_name,
        storage_state=args.storage_state,
        headless=args.headless,
        max_retries=args.max_retries,
        session_dir=session_dir,
    )

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
