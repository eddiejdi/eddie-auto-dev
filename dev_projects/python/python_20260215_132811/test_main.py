import pytest
from unittest.mock import patch, MagicMock

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        
        # Caso de sucesso com valor válido
        tarefa1.adicionar_tarefa("Lavar o café")
        assert "Lavar o café" in tarefa1.tarefas
    
    def test_adicionar_tarefa_invalido(self):
        tarefa1 = Tarefa1()
        
        # Caso de erro (divisão por zero)
        with pytest.raises(ValueError, match="Tarefa deve ser uma string"):
            tarefa1.adicionar_tarefa(123)
    
    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Lavar o café")
        tarefa1.adicionar_tarefa("Estudar Python")
        assert ["Lavar o café", "Estudar Python"] == tarefa1.listar_tarefas()
    
    def test_listar_tarefas_vazia(self):
        tarefa1 = Tarefa1()
        
        # Caso de sucesso com valores vazios
        assert [] == tarefa1.listar_tarefas()
    
    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        
        # Caso de sucesso com valor válido
        tarefa1.adicionar_tarefa("Lavar o café")
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.remover_tarefa(0)
        assert "Estudar Python" in tarefa1.tarefas
    
    def test_remover_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        
        # Caso de erro (índice de tarefa inválido)
        with pytest.raises(IndexError, match="Índice de tarefa inválido"):
            tarefa1.remover_tarefa(2)
    
    def test_salvar_tarefas(self):
        tarefa1 = Tarefa1()
        
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Lavar o café")
        tarefa1.adicionar_tarefa("Estudar Python")
        with patch('builtins.open', new_callable=MagicMock) as mock_open:
            tarefa1.salvar_tarefas("tarefas.txt")
            mock_open.assert_called_once_with("tarefas.txt", 'w')
    
    def test_salvar_tarefas_arquivo_nao_existe(self):
        tarefa1 = Tarefa1()
        
        # Caso de erro (arquivo não encontrado)
        with pytest.raises(FileNotFoundError, match="Arquivo de tarefas não encontrado"):
            tarefa1.salvar_tarefas("tarefas.txt")
    
    def test_carregar_tarefas(self):
        tarefa1 = Tarefa1()
        
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Lavar o café")
        tarefa1.adicionar_tarefa("Estudar Python")
        with patch('builtins.open', new_callable=MagicMock) as mock_open:
            mock_open.return_value.readlines = ["Lavar o café\n", "Estudar Python\n"]
            tarefa1.carregar_tarefas("tarefas.txt")
            assert ["Lavar o café", "Estudar Python"] == tarefa1.listar_tarefas()
    
    def test_carregar_tarefas_arquivo_nao_existe(self):
        tarefa1 = Tarefa1()
        
        # Caso de erro (arquivo não encontrado)
        with pytest.raises(FileNotFoundError, match="Arquivo de tarefas não encontrado"):
            tarefa1.carregar_tarefas("tarefas.txt")