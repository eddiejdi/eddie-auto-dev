#!/usr/bin/env python3
"""
Reparte um RAG monolítico em RAGs por especialidade usando Ollama.

Fluxo:
1. Lê cada registro de uma collection origem no ChromaDB.
2. Classifica a especialidade principal via Ollama (/api/generate).
3. Gera embedding via Ollama (/api/embeddings).
4. Reindexa em collections especializadas (uma por domínio).

Exemplo:
  python3 tools/repartition_rag_specialties.py \
    --source-collection chat_history \
    --source-chroma-path /home/homelab/myClaude/chroma_db \
    --target-chroma-path /home/homelab/myClaude/chroma_db \
    --ollama-url http://192.168.15.2:11434
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


DEFAULT_SPECIALTIES = [
    "backend_python",
    "backend_javascript",
    "frontend_web",
    "mobile",
    "devops_infra",
    "databases",
    "ai_ml_llm",
    "security_network",
    "automation_rpa",
    "product_business",
    "general",
]

KEYWORD_FALLBACK = {
    "backend_python": ["python", "fastapi", "django", "flask", "pip", "pytest"],
    "backend_javascript": ["node", "javascript", "typescript", "express", "nestjs"],
    "frontend_web": ["react", "vue", "angular", "css", "html", "frontend"],
    "mobile": ["android", "ios", "react native", "flutter", "kotlin", "swift"],
    "devops_infra": ["docker", "kubernetes", "terraform", "ansible", "systemd", "linux"],
    "databases": ["postgres", "mysql", "sqlite", "mongodb", "sql", "redis"],
    "ai_ml_llm": ["llm", "ollama", "rag", "embedding", "transformer", "pytorch", "tensorflow"],
    "security_network": ["vpn", "firewall", "tls", "ssl", "auth", "oauth", "security"],
    "automation_rpa": ["rpa", "automation", "workflow", "selenium", "playwright", "bot"],
    "product_business": ["produto", "negócio", "kpi", "métrica", "estratégia", "roadmap"],
}


@dataclass
class Classification:
    primary: str
    secondary: list[str]
    confidence: float
    reason: str
    used_fallback: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reparte registros de um RAG único em collections especializadas."
    )
    parser.add_argument(
        "--source-chroma-path",
        default="/home/homelab/myClaude/chroma_db",
        help="Diretório ChromaDB de origem.",
    )
    parser.add_argument(
        "--target-chroma-path",
        default="/home/homelab/myClaude/chroma_db",
        help="Diretório ChromaDB destino (pode ser o mesmo da origem).",
    )
    parser.add_argument(
        "--source-collection",
        default="chat_history",
        help="Collection monolítica de origem.",
    )
    parser.add_argument(
        "--target-prefix",
        default="specialty_",
        help="Prefixo das collections especializadas de destino.",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://192.168.15.2:11434",
        help="URL base do Ollama.",
    )
    parser.add_argument(
        "--classifier-model",
        default="qwen2.5-coder:7b",
        help="Modelo Ollama usado para classificar especialidade.",
    )
    parser.add_argument(
        "--embedding-model",
        default="nomic-embed-text",
        help="Modelo de embedding no Ollama.",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Não gera embeddings via Ollama; deixa o Chroma usar embedding padrão.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Quantidade de registros lidos por lote da origem.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Limite máximo de registros para processar (0 = todos).",
    )
    parser.add_argument(
        "--classify-max-chars",
        type=int,
        default=2200,
        help="Tamanho máximo de texto enviado ao classificador.",
    )
    parser.add_argument(
        "--embed-max-chars",
        type=int,
        default=4500,
        help="Tamanho máximo de texto enviado ao embedding.",
    )
    parser.add_argument(
        "--include-secondary",
        action="store_true",
        help="Também indexa nas especialidades secundárias retornadas.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classifica, mas não grava collections de destino.",
    )
    parser.add_argument(
        "--report-path",
        default="artifacts/rag_specialization_report.json",
        help="Caminho do relatório JSON de execução.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "general"


def sanitize_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}

    out: dict[str, Any] = {}
    for key, value in meta.items():
        clean_key = str(key)[:80]
        if isinstance(value, (str, int, float, bool)):
            out[clean_key] = value
        elif value is None:
            out[clean_key] = ""
        else:
            out[clean_key] = json.dumps(value, ensure_ascii=False)[:2000]
    return out


def trim_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...conteúdo truncado por limite de processamento...]"


def list_collection_names(client: Any) -> list[str]:
    names: list[str] = []
    for item in client.list_collections():
        names.append(item if isinstance(item, str) else item.name)
    return sorted(names)


def source_snapshot(
    document: str,
    metadata: dict[str, Any],
    max_chars: int,
) -> str:
    meta_preview = json.dumps(metadata, ensure_ascii=False)[:1200] if metadata else "{}"
    merged = f"METADATA: {meta_preview}\n\nDOCUMENTO:\n{document}"
    return trim_text(merged, max_chars)


def fallback_classification(text: str, allowed: set[str]) -> Classification:
    lowered = text.lower()
    score: dict[str, int] = {}
    for specialty, terms in KEYWORD_FALLBACK.items():
        score[specialty] = sum(1 for term in terms if term in lowered)

    best = max(score, key=score.get)
    if score[best] == 0 or best not in allowed:
        best = "general"

    secondaries = [
        key for key, value in sorted(score.items(), key=lambda x: x[1], reverse=True)
        if key != best and value > 0 and key in allowed
    ][:2]
    conf = 0.55 if best != "general" else 0.4
    reason = "Fallback por palavra-chave (Ollama indisponível ou resposta inválida)."
    return Classification(primary=best, secondary=secondaries, confidence=conf, reason=reason, used_fallback=True)


def classify_specialty(
    *,
    ollama_url: str,
    model: str,
    text: str,
    specialties: list[str],
) -> Classification:
    allowed = set(specialties)
    prompt = (
        "Você é um classificador de conhecimento para RAG.\n"
        "Classifique o texto em UMA especialidade principal e até 2 secundárias.\n"
        f"Especialidades válidas: {', '.join(specialties)}.\n"
        "Retorne somente JSON com este formato:\n"
        '{"primary":"...", "secondary":["..."], "confidence":0.0, "reason":"..."}\n'
        "Regras:\n"
        "- Use apenas especialidades válidas.\n"
        "- Se estiver ambíguo, use general.\n"
        "- confidence deve estar entre 0 e 1.\n\n"
        f"TEXTO PARA CLASSIFICAR:\n{text}"
    )

    try:
        response = requests.post(
            f"{ollama_url.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "top_p": 0.2},
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        raw = payload.get("response", "{}")
        parsed = json.loads(raw)

        primary = slugify(str(parsed.get("primary", "general")))
        if primary not in allowed:
            primary = "general"

        secondary_raw = parsed.get("secondary", [])
        if not isinstance(secondary_raw, list):
            secondary_raw = []
        secondary = []
        for item in secondary_raw:
            item_slug = slugify(str(item))
            if item_slug in allowed and item_slug != primary and item_slug not in secondary:
                secondary.append(item_slug)
        secondary = secondary[:2]

        confidence = parsed.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        reason = str(parsed.get("reason", "")).strip()[:500]
        return Classification(primary=primary, secondary=secondary, confidence=confidence, reason=reason)
    except Exception:
        return fallback_classification(text, allowed)


def ollama_embedding(ollama_url: str, model: str, text: str) -> list[float] | None:
    try:
        response = requests.post(
            f"{ollama_url.rstrip('/')}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=120,
        )
        response.raise_for_status()
        embedding = response.json().get("embedding")
        if not isinstance(embedding, list) or not embedding:
            return None
        return embedding
    except Exception:
        return None


def make_target_id(source_collection: str, source_id: str, target_collection: str) -> str:
    base = f"{source_collection}::{source_id}::{target_collection}"
    if len(base) <= 180:
        return base
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"{source_collection[:48]}::{source_id[:72]}::{target_collection[:48]}::{digest}"


def prepare_report_path(path_value: str) -> Path:
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    args = parse_args()
    specialties = [slugify(item) for item in DEFAULT_SPECIALTIES]

    try:
        import chromadb
    except ImportError as exc:
        print(
            "❌ Dependência ausente: chromadb\n"
            "Instale com: pip install chromadb requests",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    source_client = chromadb.PersistentClient(path=args.source_chroma_path)
    target_client = chromadb.PersistentClient(path=args.target_chroma_path)

    source_collections = list_collection_names(source_client)
    if args.source_collection not in source_collections:
        print(
            f"❌ Collection de origem '{args.source_collection}' não encontrada.\n"
            f"Coleções disponíveis: {', '.join(source_collections) if source_collections else '(nenhuma)'}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    source = source_client.get_collection(args.source_collection)
    total_available = source.count()
    total_to_process = total_available if args.max_records <= 0 else min(total_available, args.max_records)

    if total_to_process == 0:
        print("⚠️ Collection de origem está vazia. Nada para processar.")
        return

    print("🚀 Iniciando repartição do RAG em especialidades")
    print(f"   Origem: {args.source_collection} ({total_available} registros)")
    print(f"   Destino: prefixo '{args.target_prefix}' em {args.target_chroma_path}")
    print(f"   Ollama: {args.ollama_url}")
    print(f"   Processar: {total_to_process} registros")
    print(f"   Dry-run: {args.dry_run}")
    print(f"   Skip embedding: {args.skip_embedding}")
    print()

    indexed_by_collection: Counter[str] = Counter()
    classified_by_specialty: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    fallback_counter = 0

    processed = 0
    batch_size = max(1, args.batch_size)

    for offset in range(0, total_to_process, batch_size):
        batch_limit = min(batch_size, total_to_process - offset)
        batch = source.get(
            include=["documents", "metadatas"],
            limit=batch_limit,
            offset=offset,
        )

        ids = batch.get("ids", [])
        documents = batch.get("documents", [])
        metadatas = batch.get("metadatas", []) or [{} for _ in range(len(ids))]

        per_collection_payload: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
        )

        for idx, source_id in enumerate(ids):
            source_doc = str(documents[idx] if idx < len(documents) else "")
            source_meta = sanitize_metadata(metadatas[idx] if idx < len(metadatas) else {})

            if not source_doc.strip():
                failures.append({"source_id": source_id, "error": "documento vazio"})
                continue

            snapshot = source_snapshot(
                source_doc,
                source_meta,
                max_chars=args.classify_max_chars,
            )

            classification = classify_specialty(
                ollama_url=args.ollama_url,
                model=args.classifier_model,
                text=snapshot,
                specialties=specialties,
            )
            if classification.used_fallback:
                fallback_counter += 1

            targets = [classification.primary]
            if args.include_secondary:
                targets.extend(classification.secondary)

            targets = [slugify(item) for item in targets if item]
            if not targets:
                targets = ["general"]

            embedding: list[float] | None = None
            if not args.skip_embedding:
                embed_text = trim_text(source_doc, args.embed_max_chars)
                embedding = ollama_embedding(args.ollama_url, args.embedding_model, embed_text)
                if embedding is None:
                    failures.append({"source_id": source_id, "error": "embedding falhou"})
                    continue

            for specialty in targets:
                collection_name = f"{args.target_prefix}{specialty}"
                target_id = make_target_id(args.source_collection, str(source_id), collection_name)

                metadata = {
                    **source_meta,
                    "source_collection": args.source_collection,
                    "source_id": str(source_id),
                    "specialty_primary": classification.primary,
                    "specialty_confidence": float(classification.confidence),
                    "specialty_reason": classification.reason,
                    "specialty_indexed_at": datetime.utcnow().isoformat() + "Z",
                }

                payload = per_collection_payload[collection_name]
                payload["ids"].append(target_id)
                payload["documents"].append(source_doc)
                payload["metadatas"].append(metadata)
                if embedding is not None:
                    payload["embeddings"].append(embedding)

                indexed_by_collection[collection_name] += 1
                classified_by_specialty[specialty] += 1

            processed += 1
            if processed % 20 == 0 or processed == total_to_process:
                print(f"   Processados: {processed}/{total_to_process}")

        if not args.dry_run:
            for collection_name, payload in per_collection_payload.items():
                try:
                    collection = target_client.get_or_create_collection(name=collection_name)
                    upsert_kwargs = dict(
                        ids=payload["ids"],
                        documents=payload["documents"],
                        metadatas=payload["metadatas"],
                    )
                    if payload["embeddings"]:
                        upsert_kwargs["embeddings"] = payload["embeddings"]
                    collection.upsert(**upsert_kwargs)
                except Exception as exc:
                    for source_id in payload["ids"]:
                        failures.append(
                            {
                                "source_id": source_id,
                                "error": f"falha ao gravar {collection_name}: {exc}",
                            }
                        )

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source_collection": args.source_collection,
        "source_chroma_path": args.source_chroma_path,
        "target_chroma_path": args.target_chroma_path,
        "target_prefix": args.target_prefix,
        "ollama_url": args.ollama_url,
        "classifier_model": args.classifier_model,
        "embedding_model": args.embedding_model,
        "skip_embedding": args.skip_embedding,
        "dry_run": args.dry_run,
        "processed_records": processed,
        "available_source_records": total_available,
        "fallback_classifications": fallback_counter,
        "classified_by_specialty": dict(classified_by_specialty),
        "indexed_by_collection": dict(indexed_by_collection),
        "failures_count": len(failures),
        "failures_preview": failures[:100],
    }

    report_path = prepare_report_path(args.report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("✅ Finalizado")
    print(f"   Registros processados: {processed}")
    print(f"   Fallbacks de classificação: {fallback_counter}")
    print(f"   Falhas: {len(failures)}")
    print(f"   Relatório: {report_path}")
    if not args.dry_run:
        print("   Collections criadas/atualizadas:")
        for name, qty in sorted(indexed_by_collection.items(), key=lambda x: x[0]):
            print(f"   - {name}: {qty}")


if __name__ == "__main__":
    main()
