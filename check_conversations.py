#!/usr/bin/env python3
"""Script leve para checar conversas no Postgres (sem import pesado de chromadb)."""
import os, sys

try:
    from sqlalchemy import create_engine, text
except ImportError:
    sys.exit("sqlalchemy não instalado")

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    sys.exit("DATABASE_URL não configurado")

engine = create_engine(db_url)
with engine.connect() as c:
    total = c.execute(text("SELECT COUNT(*) FROM messages")).scalar()
    print(f"=== TESTE DE VISUALIZAÇÃO ===")
    print(f"Total mensagens no Postgres: {total}")

    rows = c.execute(text("""
        SELECT conversation_id,
               COUNT(*) as cnt,
               MIN(timestamp) as first_ts,
               MAX(timestamp) as last_ts,
               STRING_AGG(DISTINCT source, ', ') as sources
        FROM messages
        GROUP BY conversation_id
        ORDER BY last_ts DESC
        LIMIT 5
    """)).fetchall()

    print(f"Conversas distintas (top 5):")
    for r in rows:
        conv_id = r[0][:35] if r[0] else '?'
        print(f"\nConv: {conv_id}...  msgs={r[1]}  sources={r[4]}")
        print(f"  Período: {r[2]} → {r[3]}")

        msgs = c.execute(text("""
            SELECT source, target, substring(content from 1 for 80)
            FROM messages WHERE conversation_id = :cid
            ORDER BY timestamp ASC LIMIT 3
        """), {"cid": r[0]}).fetchall()
        for m in msgs:
            print(f"  [{m[0]}] ===> [{m[1]}]: {m[2]}")

    # Conversations finalizadas
    fin = c.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
    print(f"\nConversas finalizadas (tabela conversations): {fin}")

print("\n=== FIM DO TESTE ===")
