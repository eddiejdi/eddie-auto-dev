import unittest
import sqlite3
from pathlib import Path


class TestInterceptorDB(unittest.TestCase):
    def test_db_has_conversations(self):
        db_path = Path("agent_data/interceptor_data/conversations.db")
        self.assertTrue(db_path.exists(), f"DB not found at {db_path}")

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM conversations")
            cnt = cur.fetchone()[0]
        finally:
            conn.close()

        self.assertGreater(cnt, 0, "No conversations found in interceptor DB")


if __name__ == "__main__":
    unittest.main()
