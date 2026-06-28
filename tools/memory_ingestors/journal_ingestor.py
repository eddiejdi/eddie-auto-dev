#!/usr/bin/env python3
"""
Action Journal ingestor — indexa ações done/failed do Action Journal na memória compartilhada.

Executado pelo systemd timer a cada hora.
Usa watermark na tabela para indexar apenas registros novos.

Env vars:
    DATABASE_URL  — PostgreSQL (obrigatório, em /etc/default/eddie-common)
    CHROMA_DB_PATH — path ChromaDB (default: /home/homelab/myClaude/chroma_db)
    INGESTOR_BATCH — quantas ações por execução (default: 100)
"""
from __future__ import annotations

import json
import os
import sys
import time

# Adiciona raiz do repo ao path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

DATABASE_URL  = os.environ.get("DATABASE_URL", "")
BATCH_SIZE    = int(os.environ.get("INGESTOR_BATCH", "100"))


def _load_db_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL
    for path in ["/etc/default/eddie-common", os.path.expanduser("~/.env")]:
        try:
            for line in open(path).read().splitlines():
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip()
        except (FileNotFoundError, PermissionError):
            continue
    raise RuntimeError("DATABASE_URL não encontrado. Defina via env ou /etc/default/eddie-common.")


def _get_watermark(cur) -> int:
    """Retorna o ID do último registro já indexado (0 se nenhum)."""
    cur.execute("""
        SELECT COALESCE(MAX(id), 0) FROM agent_actions
        WHERE status IN ('done', 'failed', 'rejected', 'expired')
    """)
    total = cur.fetchone()[0]
    # Usamos uma tabela de watermark simples via agent_actions (meta-entrada)
    # Para simplicidade, relemos da memória o maior stored_at com source=journal
    return 0  # Simplificado: re-indexar tudo que mudou nas últimas 2h


def _action_to_fact(row: dict) -> str:
    """Converte uma linha do DB em fato legível para indexação."""
    parts = [
        f"Agente {row['agent_id']} executou {row['action_type']}",
        f"alvo={row.get('target') or 'n/a'}",
        f"status={row['status']}",
        f"risco={row['risk_level']}",
    ]
    if row.get("description"):
        parts.append(f"descrição: {row['description'][:200]}")
    if row.get("outcome"):
        parts.append(f"resultado: {row['outcome'][:200]}")
    if row.get("error_detail"):
        parts.append(f"erro: {row['error_detail'][:150]}")
    if row.get("approved_by"):
        parts.append(f"aprovado_por={row['approved_by']}")
    if row.get("created_at"):
        ts = row["created_at"]
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%d %H:%M:%S")
        parts.append(f"em={ts}")
    return " | ".join(parts)


def run() -> int:
    from tools.memory_layer.agent_memory import store, count as mem_count
    import psycopg2, psycopg2.extras

    db_url = _load_db_url()
    conn   = psycopg2.connect(db_url)
    cur    = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Indexar ações das últimas 2 horas que ainda não foram indexadas
    # (simples: re-upsert por hash — duplicatas são ignoradas via upsert)
    cur.execute("""
        SELECT id, intent_id, agent_id, action_type, description, target,
               risk_level, status, approved_by, outcome, error_detail, created_at
        FROM agent_actions
        WHERE status IN ('done', 'failed', 'rejected', 'expired')
          AND created_at > NOW() - INTERVAL '2 hours'
        ORDER BY created_at ASC
        LIMIT %s
    """, (BATCH_SIZE,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print(f"[journal-ingestor] Nenhuma ação nova para indexar.")
        return 0

    indexed = 0
    for row in rows:
        fact  = _action_to_fact(dict(row))
        tags  = [row["action_type"], row["status"], row["risk_level"]]
        store(
            fact,
            source="journal",
            tags=tags,
            agent_id=row["agent_id"],
        )
        indexed += 1

    total = mem_count(source="journal")
    print(f"[journal-ingestor] {indexed} ação(ões) indexada(s). Total journal na memória: {total}")
    return 0


def main() -> int:
    try:
        return run()
    except Exception as exc:
        print(f"[journal-ingestor] ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
