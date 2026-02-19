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

    def remover_tarefa(self, index):
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[index]

def test_adicionar_tarefa_valido():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    assert "Fazer compras" in tarefa1.listar_tarefas()

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    assert "Fazer compras" in tarefa1.listar_tarefas() and "Estudar Python" in tarefa1.listar_tarefas()

def test_remover_tarefa_valido():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.remover_tarefa(0)
    assert "Fazer compras" not in tarefa1.listar_tarefas() and "Estudar Python" in tarefa1.listar_tarefas()

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(2)

def test_remover_tarefa_indice_negativo():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)