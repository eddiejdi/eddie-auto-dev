#!/usr/bin/env python3
"""Gerenciador de memórias Copilot centralizado no PostgreSQL do homelab.

Fornece CRUD completo + busca full-text para memórias persistentes,
permitindo que qualquer agente (Copilot, Telegram, API) consulte
e atualize o contexto compartilhado.

Uso:
    from tools.copilot_memories import CopilotMemoryStore
    store = CopilotMemoryStore()
    store.upsert("repo", "grafana-access", "Admin: admin/...", tags=["infra"])
    results = store.search("grafana")
    all_user = store.list_by_scope("user")
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://eddie:eddie_memory_2026@192.168.15.2:5433/postgres",
)


class CopilotMemoryStore:
    """CRUD + busca full-text de memórias Copilot no PostgreSQL."""

    VALID_SCOPES = ("user", "repo", "session")

    def __init__(self, db_url: str | None = None) -> None:
        """Inicializa conexão com o PostgreSQL.

        Args:
            db_url: Connection string. Usa DATABASE_URL ou default se não informada.
        """
        self._db_url = db_url or DEFAULT_DB_URL

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Retorna conexão autocommit com o PostgreSQL."""
        conn = psycopg2.connect(self._db_url)
        conn.autocommit = True
        return conn

    def _validate_scope(self, scope: str) -> None:
        """Valida se o scope é permitido."""
        if scope not in self.VALID_SCOPES:
            raise ValueError(f"Scope inválido: {scope}. Use: {self.VALID_SCOPES}")

    def upsert(
        self,
        scope: str,
        key: str,
        content: str,
        tags: list[str] | None = None,
    ) -> int:
        """Insere ou atualiza uma memória.

        Args:
            scope: 'user', 'repo' ou 'session'.
            key: Identificador único (ex: 'homelab-access').
            content: Conteúdo da memória em texto/markdown.
            tags: Tags opcionais para categorização.

        Returns:
            ID do registro inserido/atualizado.
        """
        self._validate_scope(scope)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO copilot_memories (scope, key, content, tags)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (scope, key) DO UPDATE SET
                        content = EXCLUDED.content,
                        tags = EXCLUDED.tags,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (scope, key, content, tags or []),
                )
                row = cur.fetchone()
                mem_id: int = row[0] if row else 0
                logger.info(f"Memory upserted: scope={scope} key={key} id={mem_id}")
                return mem_id
        finally:
            conn.close()

    def get(self, scope: str, key: str) -> dict | None:
        """Busca uma memória pelo scope e key.

        Args:
            scope: 'user', 'repo' ou 'session'.
            key: Identificador da memória.

        Returns:
            Dicionário com dados da memória ou None.
        """
        self._validate_scope(scope)
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM copilot_memories WHERE scope = %s AND key = %s",
                    (scope, key),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def delete(self, scope: str, key: str) -> bool:
        """Remove uma memória.

        Args:
            scope: 'user', 'repo' ou 'session'.
            key: Identificador da memória.

        Returns:
            True se removida, False se não encontrada.
        """
        self._validate_scope(scope)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM copilot_memories WHERE scope = %s AND key = %s",
                    (scope, key),
                )
                deleted = cur.rowcount > 0
                if deleted:
                    logger.info(f"Memory deleted: scope={scope} key={key}")
                return deleted
        finally:
            conn.close()

    def list_by_scope(self, scope: str) -> list[dict]:
        """Lista todas as memórias de um scope.

        Args:
            scope: 'user', 'repo' ou 'session'.

        Returns:
            Lista de dicionários com dados de cada memória.
        """
        self._validate_scope(scope)
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM copilot_memories WHERE scope = %s ORDER BY updated_at DESC",
                    (scope,),
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def list_all(self) -> list[dict]:
        """Lista todas as memórias de todos os scopes.

        Returns:
            Lista de dicionários ordenada por scope e updated_at.
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM copilot_memories ORDER BY scope, updated_at DESC"
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def search(self, query: str, scope: Optional[str] = None, limit: int = 10) -> list[dict]:
        """Busca full-text em memórias usando tsquery português.

        Args:
            query: Texto de busca.
            scope: Filtrar por scope (opcional).
            limit: Máximo de resultados.

        Returns:
            Lista de memórias ordenada por relevância.
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if scope:
                    self._validate_scope(scope)
                    cur.execute(
                        """
                        SELECT *, ts_rank(
                            to_tsvector('portuguese', content),
                            plainto_tsquery('portuguese', %s)
                        ) AS rank
                        FROM copilot_memories
                        WHERE scope = %s
                          AND to_tsvector('portuguese', content)
                              @@ plainto_tsquery('portuguese', %s)
                        ORDER BY rank DESC
                        LIMIT %s
                        """,
                        (query, scope, query, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT *, ts_rank(
                            to_tsvector('portuguese', content),
                            plainto_tsquery('portuguese', %s)
                        ) AS rank
                        FROM copilot_memories
                        WHERE to_tsvector('portuguese', content)
                              @@ plainto_tsquery('portuguese', %s)
                        ORDER BY rank DESC
                        LIMIT %s
                        """,
                        (query, query, limit),
                    )
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def search_by_tag(self, tag: str) -> list[dict]:
        """Busca memórias por tag.

        Args:
            tag: Tag a buscar.

        Returns:
            Lista de memórias que contêm a tag.
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM copilot_memories WHERE %s = ANY(tags) ORDER BY updated_at DESC",
                    (tag,),
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def sync_from_files(self, memories_dir: Path, scope: str) -> int:
        """Sincroniza arquivos .md de um diretório para o banco.

        Args:
            memories_dir: Diretório contendo arquivos .md.
            scope: Scope a usar ('user' ou 'repo').

        Returns:
            Número de memórias sincronizadas.
        """
        self._validate_scope(scope)
        if not memories_dir.exists():
            logger.warning(f"Diretório não encontrado: {memories_dir}")
            return 0

        count = 0
        for md_file in sorted(memories_dir.glob("*.md")):
            key = md_file.stem
            content = md_file.read_text(encoding="utf-8")
            if content.strip():
                self.upsert(scope, key, content, tags=["file-sync", scope])
                count += 1
                logger.info(f"Synced: {scope}/{key}")

        return count

    def export_to_files(self, output_dir: Path, scope: str) -> int:
        """Exporta memórias do banco para arquivos .md.

        Args:
            output_dir: Diretório de saída.
            scope: Scope a exportar.

        Returns:
            Número de arquivos exportados.
        """
        self._validate_scope(scope)
        output_dir.mkdir(parents=True, exist_ok=True)

        memories = self.list_by_scope(scope)
        for mem in memories:
            filepath = output_dir / f"{mem['key']}.md"
            filepath.write_text(mem["content"], encoding="utf-8")

        logger.info(f"Exported {len(memories)} memories to {output_dir}")
        return len(memories)
