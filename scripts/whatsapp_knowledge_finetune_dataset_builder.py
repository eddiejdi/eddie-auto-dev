#!/usr/bin/env python3
"""Gera JSONL SFT a partir do conhecimento incremental do bot WhatsApp.

Fonte: tabela whatsapp.knowledge_facts (Postgres), populada em runtime por
scripts/misc/whatsapp_bot.py sempre que:
  - o dono corrige/ensina algo no chat (fact_type='correction')
  - o bot faz uma pesquisa web e traz resultados (fact_type='web_search')

Saída (instruction/input/output), compatível com o formato lido por
eddie_persona_finetune_peft.py:
  <out-root>/data-whatsapp-knowledge/eddie_knowledge_train.jsonl

Uso:
  DATABASE_URL=... python3 scripts/whatsapp_knowledge_finetune_dataset_builder.py \
      --out-root /home/homelab/finetune
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg2

CORRECTION_INSTRUCTION = (
    "O dono corrigiu uma resposta sua anterior no WhatsApp. "
    "Leve essa correção em conta para responder de forma coerente com ela."
)
WEB_SEARCH_INSTRUCTION = (
    "Responda usando os dados públicos encontrados numa pesquisa na web feita antes."
)


def fetch_facts(database_url: str) -> list[dict]:
    conn = psycopg2.connect(database_url)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT fact_type, query, content
            FROM whatsapp.knowledge_facts
            ORDER BY created_at ASC
            """
        )
        rows = cur.fetchall()
        return [{"fact_type": r[0], "query": r[1], "content": r[2]} for r in rows]
    finally:
        conn.close()


def to_examples(facts: list[dict]) -> list[dict]:
    examples: list[dict] = []
    for f in facts:
        content = (f.get("content") or "").strip()
        if not content:
            continue
        query = (f.get("query") or "").strip()
        if f["fact_type"] == "correction":
            examples.append(
                {
                    "instruction": CORRECTION_INSTRUCTION,
                    "input": query or "(sem contexto da resposta anterior)",
                    "output": content,
                    "fact_type": "correction",
                }
            )
        else:
            examples.append(
                {
                    "instruction": WEB_SEARCH_INSTRUCTION,
                    "input": query or "(consulta não registrada)",
                    "output": content[:2000],
                    "fact_type": "web_search",
                }
            )
    return examples


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=Path, default=Path("/home/homelab/finetune"))
    ap.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    ap.add_argument("--min-samples", type=int, default=1)
    args = ap.parse_args()

    if not args.database_url:
        raise SystemExit(
            "DATABASE_URL não definido (env var ou --database-url). "
            "Use o valor injetado pelo systemd do bot / Secrets Agent."
        )

    facts = fetch_facts(args.database_url)
    examples = to_examples(facts)

    out_dir = args.out_root / "data-whatsapp-knowledge"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "eddie_knowledge_train.jsonl"

    if len(examples) < args.min_samples:
        print(
            f"⚠️ Apenas {len(examples)} fatos aprendidos (< {args.min_samples}). "
            f"Nada escrito em {out_path}."
        )
        return 0

    with out_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")

    manifest = {
        "n": len(examples),
        "path": str(out_path),
        "corrections": sum(1 for e in examples if e["fact_type"] == "correction"),
        "web_search": sum(1 for e in examples if e["fact_type"] == "web_search"),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
