import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.tarefas

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.remover_tarefa(0)
    assert len(tarefa1.tarefas) == 0

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert tarefa1.listar_tarefas() == ["Tarefa 1", "Tarefa 2"]

def test_gerar_tarefa_aleatoria():
    tarefa1 = Tarefa1()
    nova_tarefa = tarefa1.gerar_tarefa_aleatoria()
    assert isinstance(nova_tarefa, str)

def test_adicionar_tarefa_invalida():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)