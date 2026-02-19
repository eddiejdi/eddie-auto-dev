import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert len(tarefa1.tarefas) == 1 and tarefa1.tarefas[0] == "Tarefa 1"

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.listar_tarefas()
    assert "1. Tarefa 1" in tarefa1.tarefas[0]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.remover_tarefa(1)
    assert len(tarefa1.tarefas) == 0

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    tarefa1.listar_tarefas()
    assert "Nenhuma tarefa adicionada." in tarefa1.tarefas[0]

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(2)