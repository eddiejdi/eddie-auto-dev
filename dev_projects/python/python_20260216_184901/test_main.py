import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, indice):
        if not isinstance(indice, int) or indice < 0 or indice >= len(self.tarefas):
            raise ValueError("Índice inválido")
        del self.tarefas[indice]

class TestTarefa1:
    def test_adicionar_tarefa(self, tarefa1):
        tarefa1.adicionar_tarefa("Entregar projeto")
        assert "Entregar projeto" in tarefa1.listar_tarefas()

    def test_adicionar_tarefa_invalido(self, tarefa1):
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa(123)

    def test_listar_tarefas(self, tarefa1):
        tarefa1.adicionar_tarefa("Entregar projeto")
        tarefa1.adicionar_tarefa("Lavar louça")
        assert "Entregar projeto" in tarefa1.listar_tarefas()
        assert "Lavar louça" in tarefa1.listar_tarefas()

    def test_listar_tarefas_vazia(self, tarefa1):
        assert tarefa1.listar_tarefas() == []

    def test_remover_tarefa(self, tarefa1):
        tarefa1.adicionar_tarefa("Entregar projeto")
        tarefa1.adicionar_tarefa("Lavar louça")
        tarefa1.remover_tarefa(0)
        assert "Lavar louça" in tarefa1.listar_tarefas()
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa(-1)
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa(len(tarefa1.tarefas))

    def test_remover_tarefa_indice_invalido(self, tarefa1):
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa(2)

    def test_remover_tarefa_indice_negativo(self, tarefa1):
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa(-1)