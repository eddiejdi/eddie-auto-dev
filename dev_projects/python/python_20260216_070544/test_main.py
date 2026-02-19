import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.listar_tarefas()

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.listar_tarefas()

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.remover_tarefa("Tarefa 1")
    assert len(tarefa1.listar_tarefas()) == 0

def test_remover_tarefa_inexistente():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa("Tarefa Inexistente")

def test_adicionar_tarefa_divisao_zero():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(0)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert len(tarefa1.listar_tarefas()) == 0

def test_remover_tarefa_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa("Tarefa Inexistente")