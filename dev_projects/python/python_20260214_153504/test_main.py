import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa_valido():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.listar_tarefas()

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas_valida():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert "Tarefa 1" in tarefa1.listar_tarefas() and "Tarefa 2" in tarefa1.listar_tarefas()

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert not tarefa1.listar_tarefas()

def test_remover_tarefa_valido():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.remover_tarefa(0)
    assert "Tarefa 1" not in tarefa1.listar_tarefas()

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)

def test_remover_tarefa_indice_out_of_range():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(10)