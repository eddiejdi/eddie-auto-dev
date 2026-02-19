import pytest
from unittest.mock import patch

class TestTarefa1:
    @pytest.fixture
    def tarefa1(self):
        return Tarefa1()

    def test_adicionar_tarefa(self, tarefa1):
        tarefa1.adicionar_tarefa("Fazer compras")
        assert "Fazer compras" in tarefa1.tarefas

    def test_listar_tarefas(self, tarefa1):
        tarefa1.listar_tarefas()
        # Verifique se a saída é correta (este teste depende da implementação do método listar_tarefas)

    @patch('builtins.input', return_value=0)
    def test_remover_tarefa(self, mock_input, tarefa1):
        tarefa1.remover_tarefa(0)
        assert len(tarefa1.tarefas) == 0

    def test_remove_indice_invalido(self, tarefa1):
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)

    @patch('builtins.input', return_value="2")
    def test_remover_indice_existe(self, mock_input, tarefa1):
        tarefa1.remover_tarefa(1)
        assert len(tarefa1.tarefas) == 0

    def test_remove_indice_nao_existe(self, tarefa1):
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(2)

    @patch('builtins.input', return_value="abc")
    def test_remover_indice_string(self, mock_input, tarefa1):
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa(0)