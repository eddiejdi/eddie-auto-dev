import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert tarefa1.listar_tarefas() == ["Tarefa 1"]

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert tarefa1.listar_tarefas() == ["Tarefa 1", "Tarefa 2"]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(0)
    assert tarefa1.listar_tarefas() == ["Tarefa 2"]

def test_remover_index_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)

def test_remover_index_out_of_range():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(2)

def test_adicionar_string_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(TypeError):
        tarefa1.adicionar_tarefa("")

def test_remover_string_vazia():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    with pytest.raises(TypeError):
        tarefa1.remover_tarefa("")