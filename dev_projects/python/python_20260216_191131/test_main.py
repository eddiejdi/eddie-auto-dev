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
            raise IndexError("Índice de tarefa inválido")
        del self.tarefas[index]

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    assert "Fazer compras" in tarefa1.tarefas

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar o cachorro para a praia")
    assert ["Fazer compras", "Levar o cachorro para a praia"] == tarefa1.listar_tarefas()

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert [] == tarefa1.listar_tarefas()

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar o cachorro para a praia")
    tarefa1.remover_tarefa(0)
    assert ["Levar o cachorro para a praia"] == tarefa1.listar_tarefas()

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)

def test_remover_tarefa_index_out_of_range():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(2)