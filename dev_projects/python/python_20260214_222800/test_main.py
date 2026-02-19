import pytest
from unittest.mock import patch

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert "Tarefa 1" in tarefa1.listar_tarefas()

    @patch('builtins.input', return_value="Tarefa 2")
    def test_adicionar_tarefa_with_input(self, mock_input):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa()
        assert "Tarefa 2" in tarefa1.listar_tarefas()

    @pytest.raises(ValueError)
    def test_adicionar_tarefa_invalid_type(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(123)

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        assert "Tarefa 1" in tarefa1.listar_tarefas()
        assert "Tarefa 2" in tarefa1.listar_tarefas()

    @pytest.raises(IndexError)
    def test_remover_tarefa_invalid_index(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.remover_tarefa(3)

    @patch('builtins.input', return_value="2")
    def test_remover_tarefa_with_input(self, mock_input):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        tarefa1.remover_tarefa(1)
        assert "Tarefa 1" not in tarefa1.listar_tarefas()

    @pytest.raises(IndexError)
    def test_remover_tarefa_invalid_index_with_input(self, mock_input):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.remover_tarefa(3)

    @pytest.mark.parametrize("input_value", ["0", "5"])
    def test_remover_tarefa_invalid_index_with_input(self, input_value):
        with patch('builtins.input', return_value=input_value):
            tarefa1 = Tarefa1()
            tarefa1.adicionar_tarefa("Tarefa 1")
            tarefa1.remover_tarefa(1)