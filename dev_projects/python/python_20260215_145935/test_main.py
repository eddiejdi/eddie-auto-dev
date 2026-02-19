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

    def editar_tarefa(self, index, nova_tarefa):
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        if not isinstance(nova_tarefa, str):
            raise ValueError("Nova tarefa deve ser uma string")
        self.tarefas[index] = nova_tarefa

    def __str__(self):
        return "\n".join(self.tarefas)

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    assert "Fazer compras" in tarefa1.tarefas

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    assert "Fazer compras\nEstudar Python" == tarefa1.listar_tarefas()

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.remover_tarefa(0)
    assert "Estudar Python" in tarefa1.tarefas

def test_editar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.editar_tarefa(0, "Comprar pão")
    assert "Comprar pão" in tarefa1.tarefas

def test_adicionar_tarefa_invalida():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert [] == tarefa1.listar_tarefas()

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(0)

def test_editar_tarefa_invalida():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.editar_tarefa(0, 123)