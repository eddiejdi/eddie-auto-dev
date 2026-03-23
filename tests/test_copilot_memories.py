#!/usr/bin/env python3
"""Testes unitários para tools/copilot_memories.py.

Usa mock do psycopg2 para não depender de banco real.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from tools.copilot_memories import CopilotMemoryStore


@pytest.fixture
def mock_conn():
    """Fixture que retorna mock de conexão psycopg2."""
    conn = MagicMock()
    conn.autocommit = True
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return conn, cursor


@pytest.fixture
def store():
    """Fixture que retorna CopilotMemoryStore com URL de teste."""
    return CopilotMemoryStore(db_url="postgresql://test:test@localhost:5432/testdb")


class TestUpsert:
    """Testes para o método upsert."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_upsert_inserts_with_correct_params(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Upsert deve executar INSERT ... ON CONFLICT com parâmetros corretos."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchone.return_value = (42,)

        result = store.upsert("repo", "test-key", "test content", tags=["tag1"])

        assert result == 42
        cursor.execute.assert_called_once()
        args = cursor.execute.call_args
        assert "INSERT INTO copilot_memories" in args[0][0]
        assert args[0][1] == ("repo", "test-key", "test content", ["tag1"])
        conn.close.assert_called_once()

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_upsert_default_empty_tags(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Upsert sem tags deve passar lista vazia."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchone.return_value = (1,)

        store.upsert("user", "key", "content")

        args = cursor.execute.call_args
        assert args[0][1][3] == []

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_upsert_invalid_scope_raises(self, mock_connect: MagicMock, store: CopilotMemoryStore) -> None:
        """Upsert com scope inválido deve levantar ValueError."""
        with pytest.raises(ValueError, match="Scope inválido"):
            store.upsert("invalid", "key", "content")


class TestGet:
    """Testes para o método get."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_get_existing_memory(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Get deve retornar dict quando memória existe."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        now = datetime.now(tz=timezone.utc)
        cursor.fetchone.return_value = {
            "id": 1, "scope": "repo", "key": "test",
            "content": "hello", "tags": ["a"], "created_at": now, "updated_at": now,
        }

        result = store.get("repo", "test")

        assert result is not None
        assert result["key"] == "test"
        assert result["content"] == "hello"

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_get_nonexistent_returns_none(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Get deve retornar None quando memória não existe."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchone.return_value = None

        result = store.get("repo", "nope")

        assert result is None


class TestDelete:
    """Testes para o método delete."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_delete_existing(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Delete deve retornar True quando registro é removido."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.rowcount = 1

        result = store.delete("user", "key-to-delete")

        assert result is True
        args = cursor.execute.call_args
        assert "DELETE FROM copilot_memories" in args[0][0]

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_delete_nonexistent(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Delete deve retornar False quando registro não existe."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.rowcount = 0

        result = store.delete("user", "ghost")

        assert result is False


class TestListByScope:
    """Testes para o método list_by_scope."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_list_returns_dicts(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """List deve retornar lista de dicionários."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchall.return_value = [
            {"id": 1, "scope": "repo", "key": "a", "content": "x"},
            {"id": 2, "scope": "repo", "key": "b", "content": "y"},
        ]

        result = store.list_by_scope("repo")

        assert len(result) == 2
        assert result[0]["key"] == "a"


class TestSearch:
    """Testes para o método search."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_search_with_scope(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Search com scope deve filtrar corretamente."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchall.return_value = [
            {"id": 1, "scope": "repo", "key": "grafana", "content": "...", "rank": 0.5},
        ]

        result = store.search("grafana", scope="repo")

        assert len(result) == 1
        sql = cursor.execute.call_args[0][0]
        assert "scope = %s" in sql

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_search_without_scope(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Search sem scope busca em todas as memórias."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchall.return_value = []

        result = store.search("something")

        assert result == []
        sql = cursor.execute.call_args[0][0]
        assert "scope = %s" not in sql


class TestSearchByTag:
    """Testes para o método search_by_tag."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_search_by_tag(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """search_by_tag deve buscar via ANY(tags)."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchall.return_value = [
            {"id": 1, "scope": "repo", "key": "k", "content": "c", "tags": ["infra"]},
        ]

        result = store.search_by_tag("infra")

        assert len(result) == 1
        sql = cursor.execute.call_args[0][0]
        assert "ANY(tags)" in sql


class TestSyncFromFiles:
    """Testes para o método sync_from_files."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_sync_from_files(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple, tmp_path: Path) -> None:
        """sync_from_files deve ler arquivos .md e inserir no DB."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchone.return_value = (1,)

        # Criar arquivos de teste
        (tmp_path / "note1.md").write_text("# Note 1\nContent here")
        (tmp_path / "note2.md").write_text("# Note 2\nMore content")
        (tmp_path / "readme.txt").write_text("Not a markdown file")

        count = store.sync_from_files(tmp_path, "repo")

        assert count == 2
        assert cursor.execute.call_count == 2

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_sync_nonexistent_dir(self, mock_connect: MagicMock, store: CopilotMemoryStore) -> None:
        """sync_from_files com dir inexistente deve retornar 0."""
        count = store.sync_from_files(Path("/nonexistent/dir"), "repo")
        assert count == 0


class TestExportToFiles:
    """Testes para o método export_to_files."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_export_creates_files(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple, tmp_path: Path) -> None:
        """export_to_files deve criar arquivos .md a partir do DB."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchall.return_value = [
            {"id": 1, "scope": "repo", "key": "file1", "content": "# Content 1"},
            {"id": 2, "scope": "repo", "key": "file2", "content": "# Content 2"},
        ]

        count = store.export_to_files(tmp_path / "export", "repo")

        assert count == 2
        assert (tmp_path / "export" / "file1.md").read_text() == "# Content 1"
        assert (tmp_path / "export" / "file2.md").read_text() == "# Content 2"


class TestValidateScope:
    """Testes para validação de scope."""

    def test_valid_scopes(self, store: CopilotMemoryStore) -> None:
        """Scopes válidos não devem levantar exceção."""
        for scope in ("user", "repo", "session"):
            store._validate_scope(scope)  # Não deve levantar

    def test_invalid_scope(self, store: CopilotMemoryStore) -> None:
        """Scopes inválidos devem levantar ValueError."""
        with pytest.raises(ValueError):
            store._validate_scope("global")

        with pytest.raises(ValueError):
            store._validate_scope("")


class TestConnectionManagement:
    """Testes para gestão de conexão."""

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_connection_closed_on_success(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Conexão deve ser fechada após operação bem-sucedida."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.fetchall.return_value = []

        store.list_by_scope("user")

        conn.close.assert_called_once()

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_connection_closed_on_error(self, mock_connect: MagicMock, store: CopilotMemoryStore, mock_conn: tuple) -> None:
        """Conexão deve ser fechada mesmo em caso de erro."""
        conn, cursor = mock_conn
        mock_connect.return_value = conn
        cursor.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            store.list_by_scope("user")

        conn.close.assert_called_once()

    @patch("tools.copilot_memories.psycopg2.connect")
    def test_autocommit_enabled(self, mock_connect: MagicMock, store: CopilotMemoryStore) -> None:
        """Conexão deve ter autocommit habilitado."""
        conn = MagicMock()
        mock_connect.return_value = conn
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = []

        store.list_all()

        assert conn.autocommit is True
