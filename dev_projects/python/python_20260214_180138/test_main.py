import pytest
from unittest.mock import patch, call

class TestTarefa1:
    @patch('sys.argv', ['main.py', '--adicionar', 'tarefa1'])
    def test_adicionar_tarefa(self):
        from main import main
        main()
        assert Tarefa1.tarefas == ['tarefa1']

    @patch('sys.argv', ['main.py', '--listar'])
    def test_listar_tarefas(self):
        from main import main
        main()
        assert Tarefa1.tarefas == []

    @patch('sys.argv', ['main.py', '--remover', '1'])
    def test_remover_tarefa(self):
        from main import main
        main()
        assert Tarefa1.tarefas == []