import pytest
from tarefa1 import Tarefa1

def test_add_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Tarefa 1")
    assert len(tarefa1.tarefas) == 1
    assert tarefa1.tarefas[0] == "Tarefa 1"

def test_add_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.add_tarefa(123)

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Tarefa 1")
    tarefa1.add_tarefa("Tarefa 2")
    tarefa1.listar_tarefas()
    assert "Tarefa 1" in tarefa1.tarefas
    assert "Tarefa 2" in tarefa1.tarefas

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    tarefa1.listar_tarefas()
    assert "Nenhuma tarefa encontrada." in tarefa1.tarefas

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Tarefa 1")
    tarefa1.add_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(1)
    assert len(tarefa1.tarefas) == 1
    assert tarefa1.tarefas[0] == "Tarefa 1"

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(3)

def test_sair():
    tarefa1 = Tarefa1()
    tarefa1.sair()