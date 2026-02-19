import pytest
from tarefa1 import Tarefa1

class TestTarefa1:
    def setup_method(self):
        self.tarefa1 = Tarefa1()

    def test_adicionar_tarefa_sucesso(self):
        # Caso de sucesso com valores válidos
        tarefa = "Limpar o quarto"
        self.tarefa1.adicionar_tarefa(tarefa)
        assert len(self.tarefa1.tarefas) == 1

    def test_adicionar_tarefa_erro_divisao_zero(self):
        # Caso de erro (divisão por zero)
        with pytest.raises(ZeroDivisionError):
            self.tarefa1.adicionar_tarefa("Dividir por zero")

    def test_listar_tarefas_sucesso(self):
        # Caso de sucesso com valores válidos
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Limpar o quarto")
        tarefa1.adicionar_tarefa("Lavar a louça")
        self.tarefa1.listar_tarefas()

    def test_listar_tarefas_erro_indice_invalido(self):
        # Caso de erro (índice inválido)
        with pytest.raises(IndexError):
            self.tarefa1.remover_tarefa(3)

    def test_remover_tarefa_sucesso(self):
        # Caso de sucesso com valores válidos
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Limpar o quarto")
        tarefa1.adicionar_tarefa("Lavar a louça")
        self.tarefa1.remover_tarefa(0)
        assert len(self.tarefa1.tarefas) == 1