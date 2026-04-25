#!/usr/bin/env python3
"""Utilitários para obter a última foto enviada ao bot Telegram via MCP Server.

Este módulo reutiliza o `tools.telegram_mcp_server` (MCP) quando disponível.
Fornece uma função testável `fetch_latest_photo_path` que aceita um callable
de injeção (`mcp_call`) para facilitar testes sem rede.

Todas as docstrings e mensagens em PT-BR.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Callable, Dict, Optional


def _default_mcp_call(tool: str, params: Dict) -> Dict:
    """Chamada padrão ao MCP: invoca `tools.telegram_mcp_server.call_tool`.

    Retorna o JSON já desserializado (dict). Se ocorrer erro, retorna {}
    """
    try:
        import asyncio
        from tools import telegram_mcp_server as tg

        # call_tool é async e retorna lista de TextContent; extraímos o texto JSON
        result = asyncio.run(tg.call_tool(tool, params))
        if not result:
            return {}
        first = result[0]
        text = getattr(first, "text", None) or (first.get("text") if isinstance(first, dict) else str(first))
        return json.loads(text)
    except Exception:
        return {}


def fetch_latest_photo_path(
    n: int = 20,
    analyze_media: bool = True,
    mcp_call: Optional[Callable[[str, Dict], Dict]] = None,
) -> Optional[Path]:
    """Busca a última foto nas últimas `n` mensagens via MCP e retorna o path local.

    Args:
        n: número de mensagens a varrer (padrão 20).
        analyze_media: se True, solicita análise/baixa de mídia (padrão True).
        mcp_call: callable opcional (tool_name, params) -> dict para injeção em testes.

    Retorna:
        `Path` com o arquivo local salvo pelo MCP (MEDIA_DIR) ou `None` se não encontrar.
    """
    if mcp_call is None:
        mcp_call = _default_mcp_call

    summary = mcp_call("tg_latest", {"n": n, "analyze_media": analyze_media, "only_new": False})
    if not summary:
        return None

    messages = summary.get("messages", [])
    # procurar da mais recente para trás
    for m in reversed(messages):
        if m.get("type") == "photo":
            # se já foi baixada/analizada pelo MCP, teremos local_path
            lp = m.get("local_path")
            if lp:
                return Path(lp)

            # fallback: tentar tg_analyze para forçar download
            file_id = m.get("file_id")
            if file_id:
                analyze = mcp_call("tg_analyze", {"file_id": file_id})
                if analyze and isinstance(analyze, dict):
                    lp2 = analyze.get("local_path")
                    if lp2:
                        return Path(lp2)
            return None

    return None


def main() -> int:
    """CLI: busca a última foto e opcionalmente copia para `--out`."""
    parser = argparse.ArgumentParser(description="Baixa a última foto enviada ao bot via MCP")
    parser.add_argument("--n", type=int, default=20, help="Número de mensagens a buscar")
    parser.add_argument("--no-analyze", action="store_true", help="Não analisar/baixar mídia (usa somente metadados)")
    parser.add_argument("--out", type=str, default="telegram_last_photo.jpg", help="Caminho de saída para copiar a foto (opcional)")

    args = parser.parse_args()

    path = fetch_latest_photo_path(n=args.n, analyze_media=not args.no_analyze)
    if not path:
        print("Nenhuma foto encontrada nas últimas mensagens")
        return 2

    out_path = Path(args.out)
    try:
        shutil.copy(path, out_path)
        print(f"Foto salva em: {out_path}")
        return 0
    except Exception as e:
        print(f"Falha ao copiar arquivo: {e}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
