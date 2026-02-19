import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
        else:
            raise IndexError("Índice inválido")

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    assert tarefa1.listar_tarefas() == ["Fazer compras"]

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar ao médico")
    assert tarefa1.listar_tarefas() == ["Fazer compras", "Levar ao médico"]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar ao médico")
    tarefa1.remover_tarefa(0)
    assert tarefa1.listar_tarefas() == ["Levar ao médico"]

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)

def test_remover_tarefa_indice_exceito():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(2)