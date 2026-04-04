#!/usr/bin/env python3
"""Agendador de posts orgânicos no X/Twitter — Marketing RPA4ALL.

Lê posts de marketing/ads/x_posts.json e publica via X Agent API (porta 8515).
Registra posts publicados no PostgreSQL para evitar duplicatas.

Uso:
    python3 marketing/x_post_scheduler.py              # Posta próximo pendente
    python3 marketing/x_post_scheduler.py --dry-run    # Apenas mostra qual seria postado
    python3 marketing/x_post_scheduler.py --list        # Lista status de todos os posts
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger("marketing.x_scheduler")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@192.168.15.2:5433/shared",
)
X_AGENT_URL = os.getenv("X_AGENT_URL", "http://localhost:8515")
POSTS_FILE = Path(__file__).resolve().parent / "ads" / "x_posts.json"


def _get_conn():
    """Obtém conexão PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _ensure_table() -> None:
    """Garante que a tabela de log existe."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS marketing")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS marketing.x_posts_log (
                    id          SERIAL PRIMARY KEY,
                    post_id     VARCHAR(50),
                    post_key    VARCHAR(20)     NOT NULL,
                    text        TEXT            NOT NULL,
                    posted_at   TIMESTAMPTZ     DEFAULT NOW(),
                    status      VARCHAR(50)     DEFAULT 'posted'
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_x_posts_key
                ON marketing.x_posts_log (post_key)
            """)
    finally:
        conn.close()


def _get_posted_keys() -> set[str]:
    """Retorna IDs de posts já publicados."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_key FROM marketing.x_posts_log WHERE status = 'posted'"
            )
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def _record_post(post_key: str, text: str, tweet_id: Optional[str] = None) -> None:
    """Registra post publicado no banco."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO marketing.x_posts_log (post_key, text, post_id) "
                "VALUES (%s, %s, %s)",
                (post_key, text, tweet_id),
            )
    finally:
        conn.close()


def load_posts() -> list[dict]:
    """Carrega posts do arquivo JSON."""
    if not POSTS_FILE.exists():
        logger.error("Arquivo de posts não encontrado: %s", POSTS_FILE)
        return []
    with POSTS_FILE.open() as f:
        data = json.load(f)
    # Suporta formato aninhado {"x_posts": {"posts": [...]}} ou lista direta
    if isinstance(data, dict):
        inner = data.get("x_posts", data)
        if isinstance(inner, dict):
            return inner.get("posts", [])
        return inner
    return data


def get_next_post() -> Optional[dict]:
    """Retorna o próximo post não publicado."""
    posts = load_posts()
    posted = _get_posted_keys()
    for post in posts:
        if post["id"] not in posted:
            return post
    return None


def publish_post(post: dict) -> Optional[str]:
    """Publica post via X Agent API. Retorna tweet_id ou None."""
    import urllib.request
    import urllib.error

    text = post["texto"]
    hashtags = post.get("hashtags", [])
    if hashtags:
        text += "\n\n" + " ".join(hashtags)

    payload = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        f"{X_AGENT_URL}/tweets",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            tweet_id = data.get("data", {}).get("id")
            logger.info(
                "Post %s publicado com sucesso (tweet_id=%s)",
                post["id"],
                tweet_id,
            )
            return tweet_id
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        logger.error("Erro HTTP ao publicar post %s: %s %s", post["id"], e.code, body)
        return None
    except Exception:
        logger.exception("Erro ao publicar post %s", post["id"])
        return None


def list_status() -> None:
    """Lista status de todos os posts."""
    posts = load_posts()
    posted = _get_posted_keys()
    print(f"\n{'ID':<8} {'Semana':<8} {'Tipo':<15} {'Status':<12} {'Prévia'}")
    print("-" * 80)
    for p in posts:
        status = "✅ Publicado" if p["id"] in posted else "⏳ Pendente"
        preview = p["texto"][:40] + "..." if len(p["texto"]) > 40 else p["texto"]
        print(f"{p['id']:<8} {p.get('semana', '-'):<8} {p.get('tipo', '-'):<15} {status:<12} {preview}")
    print(f"\nTotal: {len(posts)} | Publicados: {len(posted)} | Pendentes: {len(posts) - len(posted)}")


def main() -> None:
    """Entry point CLI."""
    parser = argparse.ArgumentParser(description="X/Twitter post scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra próximo post")
    parser.add_argument("--list", action="store_true", help="Lista status de todos os posts")
    args = parser.parse_args()

    _ensure_table()

    if args.list:
        list_status()
        return

    post = get_next_post()
    if not post:
        logger.info("Todos os posts já foram publicados!")
        return

    if args.dry_run:
        print(f"\n📋 Próximo post ({post['id']} — Semana {post.get('semana', '?')}):\n")
        text = post["texto"]
        hashtags = post.get("hashtags", [])
        if hashtags:
            text += "\n\n" + " ".join(hashtags)
        print(text)
        print(f"\nCaracteres: {len(text)}")
        return

    tweet_id = publish_post(post)
    if tweet_id:
        _record_post(post["id"], post["texto"], tweet_id)
        logger.info("Post %s registrado no banco", post["id"])
    else:
        logger.warning("Post %s falhou — não registrado", post["id"])
        sys.exit(1)


if __name__ == "__main__":
    main()
