import unittest
import sqlite3
from pathlib import Path
import sys
import os

# Adicionar o diretório raiz ao path para importar módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from specialized_agents.agent_interceptor import get_agent_interceptor


class TestInterceptorDB(unittest.TestCase):
    def setUp(self):
        """Setup antes de cada teste"""
        # Garantir que o interceptor seja inicializado (cria o DB se necessário)
        self.interceptor = get_agent_interceptor()

    def test_db_exists_and_has_tables(self):
        """Testa se o banco de dados existe e tem as tabelas necessárias"""
        db_path = Path("agent_data/interceptor_data/conversations.db")
        self.assertTrue(db_path.exists(), f"DB not found at {db_path}")

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        try:
            # Verificar se as tabelas existem
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            required_tables = ["conversations", "messages", "conversation_snapshots"]
            for table in required_tables:
                self.assertIn(table, tables, f"Tabela {table} não encontrada")

            # Verificar se podemos fazer queries básicas
            cur.execute("SELECT COUNT(*) FROM conversations")
            conversations_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM messages")
            messages_count = cur.fetchone()[0]

            # O teste passa se o banco existe e as tabelas funcionam
            # Não exigimos dados pré-existentes
            self.assertIsInstance(conversations_count, int)
            self.assertIsInstance(messages_count, int)

        finally:
            conn.close()

    def test_db_can_store_and_retrieve(self):
        """Testa se podemos armazenar e recuperar dados do banco"""
        # Este teste garante que o banco está funcional
        # Mesmo que vazio, deve permitir operações básicas
        db_path = Path("agent_data/interceptor_data/conversations.db")
        self.assertTrue(db_path.exists())

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        try:
            # Tentar inserir um registro de teste
            test_id = "test_conversation_123"
            cur.execute("""
                INSERT OR REPLACE INTO conversations
                (id, started_at, phase, participants, total_messages, duration_seconds, status)
                VALUES (?, datetime('now'), ?, ?, ?, ?, ?)
            """, (test_id, "testing", "test_agent", 1, 10.5, "active"))

            # Verificar se conseguimos recuperar
            cur.execute("SELECT COUNT(*) FROM conversations WHERE id = ?", (test_id,))
            count = cur.fetchone()[0]
            self.assertEqual(count, 1, "Não conseguiu inserir/recuperar dados")

            # Limpar dados de teste
            cur.execute("DELETE FROM conversations WHERE id = ?", (test_id,))
            conn.commit()

        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
