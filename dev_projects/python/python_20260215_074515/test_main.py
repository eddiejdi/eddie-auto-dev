import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.tarefas, "Tarefa não adicionada corretamente."

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.listar_tarefas()
    assert "1. Tarefa 1" in tarefa1.tarefas, "Lista de tarefas incorreta."
    assert "2. Tarefa 2" in tarefa1.tarefas, "Lista de tarefas incorreta."

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.remover_tarefa(0)
    assert len(tarefa1.tarefas) == 0, "Tarefa não removida corretamente."

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(-1)

def test_adicionar_tarefa_string_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa("")

def test_adicionar_tarefa_none():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(None)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    tarefa1.listar_tarefas()
    assert "Não há tarefas para listar." in tarefa1.tarefas, "Lista de tarefas incorreta."

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(5)