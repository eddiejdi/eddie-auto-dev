#!/usr/bin/env python3
"""
wiki_bulk_publish.py — Publica todos os .md do workspace na wiki com fila background e controle de GPU.

Fluxo:
  Fase 1 (rápida): escaneia .md → chama Ollama para gerar path/title/description → grava fila JSONL
  Fase 2 (background): lê fila → monitora GPU (porta 9835) → publica na wiki → loga resultado

Uso:
  python3 tools/wiki_bulk_publish.py                    # executa fase 1 + fase 2
  python3 tools/wiki_bulk_publish.py --phase1-only      # só gera a fila
  python3 tools/wiki_bulk_publish.py --phase2-only      # só processa fila existente
  python3 tools/wiki_bulk_publish.py --dry-run          # mostra o que seria publicado sem publicar

Thresholds de GPU (ajustados automaticamente durante execução):
  < 50% util  → delay 1s  (acelera)
  50–74% util → delay 3s  (normal)
  75–89% util → delay 8s  (desacelera)
  ≥ 90% util  → pausa 30s (back-off)
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ─── Configuração ────────────────────────────────────────────────────────────

WORKSPACE       = Path("/workspace/eddie-auto-dev")
WIKI_GQL        = "http://192.168.15.2:3009/graphql"
OLLAMA_API      = "http://192.168.15.2:11437/api/generate"
OLLAMA_MODEL    = "qwen3:8b"
GPU_EXPORTER    = "http://192.168.15.2:9835/metrics"
GPU_CHECK_EVERY = 5          # checar GPU a cada N publicações
LOG_FILE        = WORKSPACE / "logs" / f"wiki_bulk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
QUEUE_FILE      = WORKSPACE / "logs" / "wiki_publish_queue.jsonl"

WIKI_TOKEN = (
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJhcGkiOjMsImdycCI6MSwiaWF0IjoxNzczNTUzNDU0LCJleHAiOjE4MDUwODk0NTQs"
    "ImF1ZCI6InVybjp3aWtpLmpzIiwiaXNzIjoidXJuOndpa2kuanMifQ"
    ".fLRuaCR_P5X8__vQpYtMW3ASGN0Bojjm8T9rQ0Sw8rISr_hP2MJUXV3Zb8kqnjjPrXFb"
    "k8kEYUqeMlvGlEDILbf-sqAs8QxqTlwpIKbBpEqo2Z3fpzupYhcc3C5YXbZ4YToX1yDBV"
    "_9-l3Om7M80WN8HqvhSfE-TKqvRn9fJgtxRuSKBEiPrpeTWqqI2I1YzBM5sYl9sDhBfEq"
    "yQql7uzFXecoSyOxd3aQLlw9AmHghHI-2Llst-dy2vCYRC6de-XTucwEG0WlbmnhlwbQen"
    "NnfS7L-SshD6srl6cE5sG0ltMgbQipiqJ-_UH6Q0iUTjZp85QnBvYp8VUCFGyU8sEA"
)

# Thresholds → delay em segundos
GPU_THRESHOLDS = [
    (90, 30),   # ≥ 90% → pausa 30s
    (75,  8),   # ≥ 75% → delay 8s
    (50,  3),   # ≥ 50% → delay 3s
    (  0, 1),   # < 50% → delay 1s
]

# ─── Logging ─────────────────────────────────────────────────────────────────

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("wiki_bulk")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def http_json(url, payload=None, headers=None, timeout=30):
    data = json.dumps(payload).encode() if payload else None
    req = Request(url, data=data, headers=headers or {})
    if data:
        req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wiki_graphql(query, variables=None):
    return http_json(
        WIKI_GQL,
        payload={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {WIKI_TOKEN}"},
    )


def get_gpu_utilization():
    """Retorna utilização máxima entre as GPUs disponíveis (0–100)."""
    try:
        req = Request(GPU_EXPORTER)
        with urlopen(req, timeout=5) as r:
            text = r.read().decode()
        utils = re.findall(r"nvidia_smi_utilization_gpu_ratio\{[^}]+\}\s+([\d.]+)", text)
        if utils:
            return max(float(v) * 100 for v in utils)
        # fallback: memória usada / total como proxy
        used  = re.findall(r"nvidia_smi_memory_used_bytes\{[^}]+\}\s+([\d.e+]+)", text)
        total = re.findall(r"nvidia_smi_memory_total_bytes\{[^}]+\}\s+([\d.e+]+)", text)
        if used and total:
            ratios = [float(u) / float(t) * 100 for u, t in zip(used, total)]
            return max(ratios)
    except Exception as e:
        log.warning("GPU exporter inacessível: %s — assumindo 0%%", e)
    return 0.0


def delay_for_gpu(util):
    for threshold, delay in GPU_THRESHOLDS:
        if util >= threshold:
            return delay
    return 1


def gpu_status_line(util):
    bar = "█" * int(util / 5) + "░" * (20 - int(util / 5))
    level = "NORMAL" if util < 50 else "ALERTA" if util < 75 else "ALTO" if util < 90 else "CRÍTICO"
    return f"GPU [{bar}] {util:5.1f}%  [{level}]"


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[áàãâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[íìîï]", "i", text)
    text = re.sub(r"[óòõôö]", "o", text)
    text = re.sub(r"[úùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9\s/-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


# ─── Fase 1: gerar fila via Ollama ───────────────────────────────────────────

OLLAMA_PROMPT = """\
Você recebe o nome de arquivo e o início do conteúdo de um arquivo Markdown de um workspace de homelab/automação.
Retorne APENAS um JSON com os campos:
  "path": caminho wiki sem barra inicial (ex: "guides/topico", "agents/nome", "operations/descricao")
  "title": título curto da página (máx 60 chars)
  "description": descrição de uma linha (máx 120 chars)
  "tags": lista de até 3 tags relevantes

Regras para path:
- Use prefixos: agents, guides, infrastructure, operations, trading, incidents, docs
- Seja específico; evite paths genéricos como "docs/readme"
- Não repita paths já usados na lista fornecida

Arquivo: {filename}
Conteúdo (primeiros 500 chars):
{preview}

Paths já em uso (evitar duplicatas): {used_paths}

Responda SOMENTE com JSON válido, sem markdown, sem explicações.
"""


def ollama_generate_metadata(filename, preview, used_paths):
    prompt = OLLAMA_PROMPT.format(
        filename=filename,
        preview=preview[:500],
        used_paths=", ".join(list(used_paths)[-30:]),  # últimos 30 para não explodir o prompt
    )
    try:
        resp = http_json(
            OLLAMA_API,
            payload={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60,
        )
        raw = resp.get("response", "{}").strip()
        meta = json.loads(raw)
        return {
            "path":        slugify(meta.get("path", f"docs/{slugify(filename)}")),
            "title":       meta.get("title", filename)[:80],
            "description": meta.get("description", "")[:150],
            "tags":        meta.get("tags", [])[:3],
        }
    except Exception as e:
        log.warning("Ollama falhou para %s: %s — usando fallback", filename, e)
        slug = slugify(Path(filename).stem)
        return {"path": f"docs/{slug}", "title": Path(filename).stem, "description": "", "tags": []}


def phase1_build_queue(md_files, dry_run=False):
    log.info("═══ FASE 1 — Gerando fila via Ollama (%d arquivos) ═══", len(md_files))
    queue = []
    used_paths = set()

    # Carregar paths já na wiki para evitar duplicatas
    try:
        result = wiki_graphql("{ pages { list(orderBy: TITLE) { path locale } } }")
        for p in result["data"]["pages"]["list"]:
            used_paths.add(p["path"])
        log.info("Wiki atual: %d paths carregados para deduplicação", len(used_paths))
    except Exception as e:
        log.warning("Não foi possível carregar paths da wiki: %s", e)

    for i, md_path in enumerate(md_files, 1):
        rel = str(md_path.relative_to(WORKSPACE))
        try:
            content = md_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""

        preview = content[:500]
        meta = ollama_generate_metadata(rel, preview, used_paths)

        # Garantir path único
        base_path = meta["path"]
        candidate = base_path
        suffix = 2
        while candidate in used_paths:
            candidate = f"{base_path}-{suffix}"
            suffix += 1
        meta["path"] = candidate
        used_paths.add(candidate)

        item = {
            "source_file": rel,
            "path":        meta["path"],
            "title":       meta["title"],
            "description": meta["description"],
            "tags":        meta["tags"],
            "content":     content,
            "status":      "pending",
            "wiki_url":    None,
        }
        queue.append(item)

        status = "DRY" if dry_run else "FILA"
        log.info("[%s %3d/%d] %s → /pt/%s", status, i, len(md_files), rel, meta["path"])

    if not dry_run:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            for item in queue:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        log.info("Fila gravada: %s (%d itens)", QUEUE_FILE, len(queue))

    return queue


# ─── Fase 2: processar fila com controle de GPU ──────────────────────────────

CREATE_MUTATION = """
mutation($content: String! $description: String! $path: String! $title: String! $tags: [String]!) {
  pages {
    create(
      content: $content description: $description editor: "markdown"
      isPublished: true isPrivate: false locale: "pt"
      path: $path tags: $tags title: $title
    ) {
      responseResult { succeeded message }
      page { id path }
    }
  }
}
"""

UPDATE_MUTATION = """
mutation($id: Int! $content: String! $description: String! $title: String! $tags: [String]!) {
  pages {
    update(id: $id content: $content description: $description
      title: $title tags: $tags isPublished: true isPrivate: false) {
      responseResult { succeeded message }
    }
  }
}
"""


def existing_page_id(path):
    try:
        result = wiki_graphql(
            '{ pages { search(query: $q) { results { id path } } } }',
            {"q": path.split("/")[-1]},
        )
        for r in result["data"]["pages"]["search"]["results"]:
            if r["path"] == path:
                return r["id"]
    except Exception:
        pass
    return None


def publish_page(item):
    page_id = existing_page_id(item["path"])
    if page_id:
        result = wiki_graphql(UPDATE_MUTATION, {
            "id":          page_id,
            "content":     item["content"],
            "description": item["description"],
            "title":       item["title"],
            "tags":        item["tags"],
        })
        ok = result["data"]["pages"]["update"]["responseResult"]["succeeded"]
        action = "ATUALIZADO"
    else:
        result = wiki_graphql(CREATE_MUTATION, {
            "content":     item["content"],
            "description": item["description"],
            "path":        item["path"],
            "title":       item["title"],
            "tags":        item["tags"],
        })
        rc = result["data"]["pages"]["create"]
        ok = rc["responseResult"]["succeeded"]
        action = "CRIADO"

    return ok, action


def update_queue_status(idx, status, wiki_url=None):
    """Reescreve o item na posição idx do JSONL com novo status."""
    try:
        lines = QUEUE_FILE.read_text(encoding="utf-8").splitlines()
        item = json.loads(lines[idx])
        item["status"] = status
        if wiki_url:
            item["wiki_url"] = wiki_url
        lines[idx] = json.dumps(item, ensure_ascii=False)
        QUEUE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def phase2_process_queue(queue_items, dry_run=False):
    log.info("═══ FASE 2 — Processando fila (%d itens) ═══", len(queue_items))

    published = 0
    skipped   = 0
    errors    = 0
    current_delay = 3.0

    for i, item in enumerate(queue_items):
        if item.get("status") in ("done", "skipped"):
            skipped += 1
            continue

        # Monitorar GPU a cada N itens
        if i % GPU_CHECK_EVERY == 0:
            util = get_gpu_utilization()
            new_delay = delay_for_gpu(util)
            if new_delay != current_delay:
                log.info("⚡ Threshold ajustado: %.1fs → %.1fs  %s", current_delay, new_delay, gpu_status_line(util))
                current_delay = new_delay
            else:
                log.info("   %s  delay=%.1fs", gpu_status_line(util), current_delay)

            # Back-off severo
            if util >= 90:
                log.warning("🔴 GPU crítica (%.1f%%) — pausa %ds", util, current_delay)
                time.sleep(current_delay)
                continue

        wiki_url = f"https://wiki.rpa4all.com/pt/{item['path']}"

        if dry_run:
            log.info("[DRY %3d] %s → %s", i + 1, item["source_file"], wiki_url)
            continue

        try:
            ok, action = publish_page(item)
            if ok:
                published += 1
                update_queue_status(i, "done", wiki_url)
                # Link clicável no terminal via ANSI OSC 8
                link = f"\033]8;;{wiki_url}\033\\{wiki_url}\033]8;;\033\\"
                log.info("✅ [%3d/%d] %s  %s  %s",
                         i + 1, len(queue_items), action, item["title"][:50], link)
            else:
                errors += 1
                update_queue_status(i, "error")
                log.error("❌ [%3d/%d] FALHA  %s", i + 1, len(queue_items), item["path"])
        except Exception as e:
            errors += 1
            update_queue_status(i, "error")
            log.error("❌ [%3d/%d] EXCEÇÃO  %s: %s", i + 1, len(queue_items), item["path"], e)

        time.sleep(current_delay)

    log.info("═══ CONCLUÍDO: %d publicados | %d erros | %d ignorados ═══",
             published, errors, skipped)
    log.info("Log completo: %s", LOG_FILE)
    return published, errors


# ─── Entrypoint ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Publica todos os .md na wiki com controle de GPU")
    parser.add_argument("--phase1-only", action="store_true", help="Só gera a fila via Ollama")
    parser.add_argument("--phase2-only", action="store_true", help="Só processa fila existente")
    parser.add_argument("--dry-run",     action="store_true", help="Simula sem publicar")
    parser.add_argument("--limit",       type=int, default=0,  help="Limitar a N arquivos (0 = todos)")
    parser.add_argument("--workspace",   default=str(WORKSPACE), help="Caminho do workspace")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    log.info("Workspace: %s", workspace)
    log.info("Log: %s", LOG_FILE)
    log.info("Fila: %s", QUEUE_FILE)

    if not args.phase2_only:
        # Fase 1: encontrar .md e gerar fila
        exclude = {".git", "node_modules", "__pycache__", ".venv", "venv"}
        md_files = [
            p for p in workspace.rglob("*.md")
            if not any(part in exclude for part in p.parts)
        ]
        md_files.sort()
        if args.limit:
            md_files = md_files[:args.limit]
        log.info("Encontrados %d arquivos .md", len(md_files))

        queue = phase1_build_queue(md_files, dry_run=args.dry_run)
    else:
        # Carregar fila existente
        if not QUEUE_FILE.exists():
            log.error("Fila não encontrada: %s — execute sem --phase2-only primeiro", QUEUE_FILE)
            sys.exit(1)
        with open(QUEUE_FILE, encoding="utf-8") as f:
            queue = [json.loads(line) for line in f if line.strip()]
        log.info("Fila carregada: %d itens", len(queue))

    if not args.phase1_only:
        phase2_process_queue(queue, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
