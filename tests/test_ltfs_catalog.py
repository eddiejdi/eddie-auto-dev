"""
Testes unitários para tools/ltfs_catalog/catalog.py

Cobre: conexão, schema, registrar_fita, listar_fitas,
       _caminhos_ltfs, indexar, buscar, buscar_duplicados,
       _obter_database_url, CLI handlers.

Todos os IOs externos (psycopg2, os.walk, xattr) são mockados.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from stat import S_IFREG
from types import SimpleNamespace
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

# Garante que o pacote do projeto é importável
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.ltfs_catalog.catalog as catalog


# ---------------------------------------------------------------------------
# Fixtures de conexão mockada
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_conn():
    """Retorna um objeto connection simulado com cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.autocommit = True
    return conn, cursor


# ---------------------------------------------------------------------------
# conectar()
# ---------------------------------------------------------------------------

class TestConectar:
    def test_cria_conexao_com_autocommit(self):
        """conectar() deve retornar conexão com autocommit=True."""
        fake_conn = MagicMock()
        with patch("tools.ltfs_catalog.catalog.psycopg2.connect", return_value=fake_conn) as mock_connect:
            result = catalog.conectar("postgresql://user:pass@host/db")

        mock_connect.assert_called_once_with("postgresql://user:pass@host/db")
        assert fake_conn.autocommit is True
        assert result is fake_conn


# ---------------------------------------------------------------------------
# criar_schema()
# ---------------------------------------------------------------------------

class TestCriarSchema:
    def test_executa_migration_sql(self, mock_conn):
        """criar_schema() deve executar o SQL de migration completo."""
        conn, cursor = mock_conn
        catalog.criar_schema(conn)
        cursor.execute.assert_called_once_with(catalog._MIGRATION_SQL)

    def test_migration_sql_contem_tabelas_necessarias(self):
        """_MIGRATION_SQL deve criar tabelas tapes e files."""
        sql = catalog._MIGRATION_SQL
        assert "CREATE TABLE IF NOT EXISTS tape_catalog.tapes" in sql
        assert "CREATE TABLE IF NOT EXISTS tape_catalog.files" in sql

    def test_migration_sql_contem_indices_gin(self):
        """_MIGRATION_SQL deve criar índex GIN para busca full-text."""
        assert "USING gin" in catalog._MIGRATION_SQL
        assert "to_tsvector" in catalog._MIGRATION_SQL


# ---------------------------------------------------------------------------
# registrar_fita()
# ---------------------------------------------------------------------------

class TestRegistrarFita:
    def test_insert_com_todos_os_campos(self, mock_conn):
        """registrar_fita() deve executar UPSERT com todos os parâmetros."""
        conn, cursor = mock_conn
        catalog.registrar_fita(conn, "NC0322", label="NAS-LTO6-001", drive_id="HUJ5485716")

        cursor.execute.assert_called_once()
        args = cursor.execute.call_args[0]
        params = args[1]
        assert params[0] == "NC0322"
        assert params[1] == "NAS-LTO6-001"
        assert params[2] == "HUJ5485716"
        assert params[3] == "active"

    def test_insert_sem_label_e_drive(self, mock_conn):
        """registrar_fita() deve aceitar serial mínimo sem label/drive."""
        conn, cursor = mock_conn
        catalog.registrar_fita(conn, "NC0323")

        args = cursor.execute.call_args[0]
        params = args[1]
        assert params[0] == "NC0323"
        assert params[1] is None
        assert params[2] is None

    def test_sql_usa_on_conflict_upsert(self, mock_conn):
        """SQL deve usar ON CONFLICT ... DO UPDATE para UPSERT."""
        conn, cursor = mock_conn
        catalog.registrar_fita(conn, "NC0322")

        sql = cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql

    def test_status_customizado(self, mock_conn):
        """registrar_fita() deve aceitar status customizado."""
        conn, cursor = mock_conn
        catalog.registrar_fita(conn, "NC0321", status="offsite")

        params = cursor.execute.call_args[0][1]
        assert params[3] == "offsite"


# ---------------------------------------------------------------------------
# listar_fitas()
# ---------------------------------------------------------------------------

class TestListarFitas:
    def test_retorna_lista_de_dicts(self, mock_conn):
        """listar_fitas() deve retornar lista de dicionários com chaves esperadas."""
        conn, cursor = mock_conn
        now = datetime.now(timezone.utc)
        cursor.fetchall.return_value = [
            ("NC0322", "NAS-LTO6-001", "HUJ5485716", "active", now, 150, 85899345920),
        ]

        result = catalog.listar_fitas(conn)

        assert len(result) == 1
        r = result[0]
        assert r["serial"] == "NC0322"
        assert r["label"] == "NAS-LTO6-001"
        assert r["total_arquivos"] == 150
        assert r["total_bytes"] == 85899345920

    def test_retorna_lista_vazia_sem_fitas(self, mock_conn):
        """listar_fitas() deve retornar lista vazia se não houver fitas."""
        conn, cursor = mock_conn
        cursor.fetchall.return_value = []

        result = catalog.listar_fitas(conn)

        assert result == []

    def test_sql_usa_left_join_e_group_by(self, mock_conn):
        """SQL deve usar LEFT JOIN para incluir fitas sem arquivos."""
        conn, cursor = mock_conn
        cursor.fetchall.return_value = []
        catalog.listar_fitas(conn)

        sql = cursor.execute.call_args[0][0]
        assert "LEFT JOIN" in sql
        assert "GROUP BY" in sql


# ---------------------------------------------------------------------------
# _caminhos_ltfs()
# ---------------------------------------------------------------------------

class TestCaminhosLtfs:
    def test_gera_arquivos_com_metadados(self, tmp_path):
        """_caminhos_ltfs() deve gerar tuplas (path, size, mtime, ltfs_uid)."""
        arq = tmp_path / "subdir" / "arquivo.tar"
        arq.parent.mkdir(parents=True)
        arq.write_bytes(b"x" * 1024)

        with patch("os.getxattr", return_value=b"ltfs-uid-abc"):
            resultados = list(catalog._caminhos_ltfs(str(tmp_path)))

        assert len(resultados) == 1
        rel, size, mtime, uid = resultados[0]
        assert rel == "subdir/arquivo.tar"
        assert size == 1024
        assert isinstance(mtime, float)
        assert uid == "ltfs-uid-abc"

    def test_ignora_erro_de_stat(self, tmp_path):
        """_caminhos_ltfs() deve ignorar arquivos inacessíveis silenciosamente."""
        arq = tmp_path / "inacessivel.tar"
        arq.write_bytes(b"x")

        with patch.object(Path, "stat", side_effect=OSError("permissão negada")):
            resultados = list(catalog._caminhos_ltfs(str(tmp_path)))

        assert resultados == []

    def test_uid_none_quando_xattr_falha(self, tmp_path):
        """_caminhos_ltfs() deve retornar ltfs_uid=None se getxattr falhar."""
        arq = tmp_path / "arquivo.dat"
        arq.write_bytes(b"dados")

        with patch("os.getxattr", side_effect=OSError("sem xattr")):
            resultados = list(catalog._caminhos_ltfs(str(tmp_path)))

        assert len(resultados) == 1
        _, _, _, uid = resultados[0]
        assert uid is None

    def test_diretorio_vazio_gera_nada(self, tmp_path):
        """_caminhos_ltfs() deve gerar zero resultados em diretório vazio."""
        resultados = list(catalog._caminhos_ltfs(str(tmp_path)))
        assert resultados == []


# ---------------------------------------------------------------------------
# indexar()
# ---------------------------------------------------------------------------

class TestIndexar:
    def test_retorna_total_de_arquivos(self, mock_conn):
        """indexar() deve retornar o número total de arquivos processados."""
        conn, cursor = mock_conn

        fake_files = [
            ("dir/arq1.tar", 1024, 1700000000.0, "uid1"),
            ("dir/arq2.tar", 2048, 1700000001.0, "uid2"),
            ("dir/arq3.tar", 512, 1700000002.0, None),
        ]

        with patch("tools.ltfs_catalog.catalog._caminhos_ltfs", return_value=iter(fake_files)):
            total = catalog.indexar(conn, "NC0322", "/mnt/tape/lto6")

        assert total == 3

    def test_chama_executemany_com_upsert(self, mock_conn):
        """indexar() deve chamar executemany com SQL de UPSERT contendo serial e path."""
        conn, cursor = mock_conn

        # Captura as rows antes do batch.clear() via side_effect
        captured_rows: list = []

        def capture_executemany(sql: str, rows: list) -> None:
            captured_rows.extend(list(rows))  # copia antes de ser limpa

        cursor.executemany.side_effect = capture_executemany

        fake_files = [("arq.tar", 100, 1700000000.0, "uid-x")]

        with patch("tools.ltfs_catalog.catalog._caminhos_ltfs", return_value=iter(fake_files)):
            catalog.indexar(conn, "NC0322", "/mnt/tape/lto6")

        cursor.executemany.assert_called_once()
        sql = cursor.executemany.call_args[0][0]
        assert "ON CONFLICT" in sql
        assert captured_rows[0][0] == "NC0322"
        assert captured_rows[0][1] == "arq.tar"

    def test_flush_em_batches(self, mock_conn):
        """indexar() deve fazer flush a cada batch_size arquivos."""
        conn, cursor = mock_conn

        fake_files = [
            (f"arq{i}.tar", 100, float(1700000000 + i), None)
            for i in range(10)
        ]

        with patch("tools.ltfs_catalog.catalog._caminhos_ltfs", return_value=iter(fake_files)):
            total = catalog.indexar(conn, "NC0322", "/mnt/tape/lto6", batch_size=3)

        # 10 arquivos em batches de 3: 3 flushes (3,3,3) + 1 final (1) = 4 calls
        assert cursor.executemany.call_count == 4
        assert total == 10

    def test_indexar_sem_arquivos_retorna_zero(self, mock_conn):
        """indexar() com diretório vazio deve retornar 0."""
        conn, cursor = mock_conn

        with patch("tools.ltfs_catalog.catalog._caminhos_ltfs", return_value=iter([])):
            total = catalog.indexar(conn, "NC0322", "/mnt/tape/lto6")

        assert total == 0
        cursor.executemany.assert_not_called()


# ---------------------------------------------------------------------------
# buscar()
# ---------------------------------------------------------------------------

class TestBuscar:
    def test_busca_sem_filtro_de_fita(self, mock_conn):
        """buscar() sem tape_serial deve usar SQL sem filtro por fita."""
        conn, cursor = mock_conn
        now = datetime.now(timezone.utc)
        cursor.fetchall.return_value = [
            ("NC0322", "backups/jan/arquivo.tar.gz", 104857600, now),
        ]

        result = catalog.buscar(conn, "arquivo")

        assert len(result) == 1
        assert result[0]["tape"] == "NC0322"
        assert result[0]["path"] == "backups/jan/arquivo.tar.gz"

        sql = cursor.execute.call_args[0][0]
        assert "tape_serial = %s" not in sql

    def test_busca_com_filtro_de_fita(self, mock_conn):
        """buscar() com tape_serial deve filtrar pelo serial da fita."""
        conn, cursor = mock_conn
        cursor.fetchall.return_value = []

        catalog.buscar(conn, "relatorio", tape_serial="NC0322", limite=10)

        sql, params = cursor.execute.call_args[0]
        assert "tape_serial = %s" in sql
        assert params[0] == "NC0322"
        assert params[1] == "relatorio"
        assert params[2] == 10

    def test_retorna_lista_vazia_sem_resultados(self, mock_conn):
        """buscar() deve retornar lista vazia quando não encontrar nada."""
        conn, cursor = mock_conn
        cursor.fetchall.return_value = []

        result = catalog.buscar(conn, "inexistente")

        assert result == []

    def test_sql_usa_plainto_tsquery(self, mock_conn):
        """SQL de busca deve usar plainto_tsquery para GIN index."""
        conn, cursor = mock_conn
        cursor.fetchall.return_value = []

        catalog.buscar(conn, "relatorio")

        sql = cursor.execute.call_args[0][0]
        assert "plainto_tsquery" in sql
        assert "to_tsvector" in sql


# ---------------------------------------------------------------------------
# buscar_duplicados()
# ---------------------------------------------------------------------------

class TestBuscarDuplicados:
    def test_retorna_duplicados_entre_fitas(self, mock_conn):
        """buscar_duplicados() deve retornar arquivos com sha256 em múltiplas fitas."""
        conn, cursor = mock_conn
        cursor.fetchall.return_value = [
            ("sha256abc", ["NC0322:backup.tar", "NC0323:backup.tar"], 2),
        ]

        result = catalog.buscar_duplicados(conn)

        assert len(result) == 1
        assert result[0]["sha256"] == "sha256abc"
        assert result[0]["total"] == 2

    def test_sql_filtra_por_distinct_tape_serial(self, mock_conn):
        """SQL deve usar HAVING COUNT(DISTINCT tape_serial) > 1."""
        conn, cursor = mock_conn
        cursor.fetchall.return_value = []

        catalog.buscar_duplicados(conn)

        sql = cursor.execute.call_args[0][0]
        assert "DISTINCT tape_serial" in sql
        assert "sha256 IS NOT NULL" in sql


# ---------------------------------------------------------------------------
# _obter_database_url()
# ---------------------------------------------------------------------------

class TestObterDatabaseUrl:
    def test_lê_variavel_tape_catalog_db(self):
        """_obter_database_url() deve retornar TAPE_CATALOG_DB da env."""
        with patch.dict(os.environ, {"TAPE_CATALOG_DB": "postgresql://test/db"}):
            url = catalog._obter_database_url()
        assert url == "postgresql://test/db"

    def test_lê_database_url_como_fallback(self):
        """_obter_database_url() deve usar DATABASE_URL se TAPE_CATALOG_DB ausente."""
        env = {"DATABASE_URL": "postgresql://fallback/db"}
        with patch.dict(os.environ, env, clear=True):
            # remove TAPE_CATALOG_DB se existir
            os.environ.pop("TAPE_CATALOG_DB", None)
            url = catalog._obter_database_url()
        assert url == "postgresql://fallback/db"

    def test_lê_arquivo_env_quando_env_vazio(self, tmp_path):
        """_obter_database_url() deve ler /etc/ltfs-catalog.env se env vazia."""
        env_file = tmp_path / "ltfs-catalog.env"
        env_file.write_text('TAPE_CATALOG_DB="postgresql://file/db"\n')

        clean_env = {k: v for k, v in os.environ.items() if k not in ("TAPE_CATALOG_DB", "DATABASE_URL")}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("tools.ltfs_catalog.catalog.Path") as mock_path:
                mock_env_path = MagicMock()
                mock_env_path.exists.return_value = True
                mock_env_path.read_text.return_value = 'TAPE_CATALOG_DB=postgresql://file/db\n'
                mock_path.return_value = mock_env_path

                url = catalog._obter_database_url()

        assert url == "postgresql://file/db"

    def test_retorna_string_vazia_sem_configuracao(self):
        """_obter_database_url() deve retornar '' se nada configurado."""
        clean_env = {k: v for k, v in os.environ.items() if k not in ("TAPE_CATALOG_DB", "DATABASE_URL")}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("tools.ltfs_catalog.catalog.Path") as mock_path:
                mock_env_path = MagicMock()
                mock_env_path.exists.return_value = False
                mock_path.return_value = mock_env_path

                url = catalog._obter_database_url()

        assert url == ""


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------

class TestCmdIndex:
    def test_cmd_index_executa_fluxo_completo(self):
        """_cmd_index() deve: conectar, criar_schema, registrar_fita, indexar."""
        args = SimpleNamespace(
            tape="NC0322",
            label="LTO6-001",
            drive_id="HUJ5485716",
            mountpoint="/mnt/tape/lto6",
            batch_size=500,
        )
        fake_conn = MagicMock()

        with patch("tools.ltfs_catalog.catalog._obter_database_url", return_value="postgresql://x/y"), \
             patch("tools.ltfs_catalog.catalog.conectar", return_value=fake_conn) as mock_conn, \
             patch("tools.ltfs_catalog.catalog.criar_schema") as mock_schema, \
             patch("tools.ltfs_catalog.catalog.registrar_fita") as mock_reg, \
             patch("tools.ltfs_catalog.catalog.indexar", return_value=42) as mock_idx, \
             patch("builtins.print") as mock_print:
            catalog._cmd_index(args)

        mock_conn.assert_called_once_with("postgresql://x/y")
        mock_schema.assert_called_once_with(fake_conn)
        mock_reg.assert_called_once_with(fake_conn, "NC0322", label="LTO6-001", drive_id="HUJ5485716")
        mock_idx.assert_called_once_with(fake_conn, "NC0322", "/mnt/tape/lto6", batch_size=500)
        mock_print.assert_called_once()

    def test_cmd_index_sai_sem_database_url(self):
        """_cmd_index() deve chamar sys.exit se DATABASE_URL não estiver configurada."""
        args = SimpleNamespace(tape="NC0322", label=None, drive_id=None,
                               mountpoint="/mnt/tape/lto6", batch_size=500)

        with patch("tools.ltfs_catalog.catalog._obter_database_url", return_value=""), \
             pytest.raises(SystemExit):
            catalog._cmd_index(args)


class TestCmdQuery:
    def test_cmd_query_exibe_resultados(self, capsys):
        """_cmd_query() deve imprimir resultados encontrados."""
        args = SimpleNamespace(termo="backup", tape=None, limit=10)
        now = datetime.now(timezone.utc)
        fake_conn = MagicMock()
        fake_results = [
            {"tape": "NC0322", "path": "backups/jan.tar.gz", "size": 1073741824, "mtime": now},
        ]

        with patch("tools.ltfs_catalog.catalog._obter_database_url", return_value="postgresql://x/y"), \
             patch("tools.ltfs_catalog.catalog.conectar", return_value=fake_conn), \
             patch("tools.ltfs_catalog.catalog.buscar", return_value=fake_results):
            catalog._cmd_query(args)

        captured = capsys.readouterr()
        assert "NC0322" in captured.out
        assert "backups/jan.tar.gz" in captured.out

    def test_cmd_query_exibe_nenhum_resultado(self, capsys):
        """_cmd_query() deve informar quando não há resultados."""
        args = SimpleNamespace(termo="xyz_nao_existe", tape=None, limit=10)
        fake_conn = MagicMock()

        with patch("tools.ltfs_catalog.catalog._obter_database_url", return_value="postgresql://x/y"), \
             patch("tools.ltfs_catalog.catalog.conectar", return_value=fake_conn), \
             patch("tools.ltfs_catalog.catalog.buscar", return_value=[]):
            catalog._cmd_query(args)

        captured = capsys.readouterr()
        assert "Nenhum" in captured.out


class TestCmdList:
    def test_cmd_list_exibe_fitas(self, capsys):
        """_cmd_list() deve exibir tabela de fitas."""
        args = SimpleNamespace()
        now = datetime.now(timezone.utc)
        fake_conn = MagicMock()
        fake_fitas = [
            {"serial": "NC0322", "label": "LTO6-001", "drive_id": "HUJ", "status": "active",
             "last_seen": now, "total_arquivos": 150, "total_bytes": 85899345920},
        ]

        with patch("tools.ltfs_catalog.catalog._obter_database_url", return_value="postgresql://x/y"), \
             patch("tools.ltfs_catalog.catalog.conectar", return_value=fake_conn), \
             patch("tools.ltfs_catalog.catalog.listar_fitas", return_value=fake_fitas):
            catalog._cmd_list(args)

        captured = capsys.readouterr()
        assert "NC0322" in captured.out
        assert "active" in captured.out

    def test_cmd_list_sem_fitas(self, capsys):
        """_cmd_list() deve informar quando catalog está vazio."""
        args = SimpleNamespace()
        fake_conn = MagicMock()

        with patch("tools.ltfs_catalog.catalog._obter_database_url", return_value="postgresql://x/y"), \
             patch("tools.ltfs_catalog.catalog.conectar", return_value=fake_conn), \
             patch("tools.ltfs_catalog.catalog.listar_fitas", return_value=[]):
            catalog._cmd_list(args)

        captured = capsys.readouterr()
        assert "Nenhuma" in captured.out
