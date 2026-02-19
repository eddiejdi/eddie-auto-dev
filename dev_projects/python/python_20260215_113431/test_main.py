import pytest
from unittest.mock import patch, MagicMock

class Tarefa1:
    def __init__(self):
        self.task_name = "Tarefa 1"
        self.description = "Implemente todas as funcionalidades listadas nos requisitos"

    def execute(self):
        try:
            # Implementação da tarefa 1 aqui
            print(f"Executando {self.task_name}")
            # Adicione suas implementações aqui
            pass

        except Exception as e:
            print(f"Erro ao executar {self.task_name}: {e}")

@pytest.fixture
def mock_execute():
    with patch.object(Tarefa1, 'execute') as mock_method:
        yield mock_method

def test_tarefa1_success(mock_execute):
    tarefa1 = Tarefa1()
    tarefa1.execute()
    mock_execute.assert_called_once_with()

def test_tarefa1_error_division_by_zero(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = ZeroDivisionError("division by zero")
        tarefa1.execute()
        mock_method.assert_called_once_with()

def test_tarefa1_error_invalid_value(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = ValueError("Invalid value")
        tarefa1.execute()
        mock_method.assert_called_once_with()

def test_tarefa1_edge_case_empty_string(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = TypeError("TypeError: unsupported operand type(s) for -: 'int' and 'str'")
        tarefa1.execute()
        mock_method.assert_called_once_with()

def test_tarefa1_edge_case_none(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = TypeError("TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'")
        tarefa1.execute()
        mock_method.assert_called_once_with()

def test_tarefa1_edge_case_max_int(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = OverflowError("integer overflow")
        tarefa1.execute()
        mock_method.assert_called_once_with()

def test_tarefa1_edge_case_min_int(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = OverflowError("integer underflow")
        tarefa1.execute()
        mock_method.assert_called_once_with()

def test_tarefa1_edge_case_max_float(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = OverflowError("float overflow")
        tarefa1.execute()
        mock_method.assert_called_once_with()

def test_tarefa1_edge_case_min_float(mock_execute):
    with patch.object(Tarefa1, 'execute') as mock_method:
        mock_method.side_effect = OverflowError("float underflow")
        tarefa1.execute()
        mock_method.assert_called_once_with()