import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.tarefas, "Tarefa não adicionada corretamente"

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert tarefa1.listar_tarefas() == "Tarefa 1\nTarefa 2", "Lista de tarefas incorreta"

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(0)
    assert "Tarefa 2" in tarefa1.tarefas, "Tarefa não removida corretamente"

def test_adicionar_invalida():
    with pytest.raises(ValueError):
        Tarefa1().adicionar_tarefa(123)

def test_listar_vazia():
    tarefa1 = Tarefa1()
    assert tarefa1.listar_tarefas() == "", "Lista de tarefas não vazia"

def test_remover_invalido():
    with pytest.raises(ValueError):
        Tarefa1().remover_tarefa(0)

def test_adicionar_string_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa("")

def test_listar_string_vazia():
    tarefa1 = Tarefa1()
    assert tarefa1.listar_tarefas() == "", "Lista de tarefas não vazia"

def test_remover_string_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(0)