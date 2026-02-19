import pytest
from unittest.mock import patch

class TestTarefa1:
    @pytest.fixture
    def tarefa1(self):
        return Tarefa1()

    def test_adicionar_tarefa(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert "Tarefa 1" in tarefa1.listar_tarefas()

    def test_listar_tarefas(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        assert "Tarefa 1" in tarefa1.listar_tarefas()
        assert "Tarefa 2" in tarefa1.listar_tarefas()

    def test_remover_tarefa(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.remover_tarefa(0)
        assert "Tarefa 2" in tarefa1.listar_tarefas()

    def test_remover_indice_invalido(self, tarefa1):
        # Caso de erro com índice inválido
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)

    @patch('builtins.input', return_value='Tarefa 3')
    def test_adicionar_tarefa_input(self, mock_input, tarefa1):
        # Caso de sucesso com entrada do usuário
        tarefa1.adicionar_tarefa()
        assert "Tarefa 3" in tarefa1.listar_tarefas()

    @patch('builtins.input', return_value='1')
    def test_remover_tarefa_input(self, mock_input, tarefa1):
        # Caso de sucesso com entrada do usuário
        tarefa1.adicionar_tarefa()
        tarefa1.remover_tarefa(0)
        assert "Tarefa 2" in tarefa1.listar_tarefas()

    def test_listar_vazio(self, tarefa1):
        # Caso de sucesso com lista vazia
        assert tarefa1.listar_tarefas() == []

    @patch('builtins.input', return_value='')
    def test_remover_indice_vazio(self, mock_input, tarefa1):
        # Caso de erro com índice vazio
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(0)

    @patch('builtins.input', return_value='abc')
    def test_adicionar_tarefa_invalido(self, mock_input, tarefa1):
        # Caso de erro com valor inválido
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa("abc")

    @patch('builtins.input', return_value='-1')
    def test_remover_indice_negativo(self, mock_input, tarefa1):
        # Caso de erro com índice negativo
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)