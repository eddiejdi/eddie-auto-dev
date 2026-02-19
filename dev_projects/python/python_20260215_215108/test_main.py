import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert len(tarefa1.listar_tarefas()) == 1, "Tarefa não adicionada corretamente"

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert tarefa1.listar_tarefas() == ["Tarefa 1", "Tarefa 2"], "Lista de tarefas incorreta"

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(0)
    assert len(tarefa1.listar_tarefas()) == 1, "Tarefa removida incorretamente"

def test_remover_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(-1)

def test_adicionar_string_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa("")

def test_remover_indice_negativo():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(-2)

def test_adicionar_inteiro():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)