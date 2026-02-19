import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o carro")
    assert "Lavar o carro" in tarefa1.tarefas

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o carro")
    tarefa1.adicionar_tarefa("Estudar Python")
    assert tarefa1.listar_tarefas() == ["Lavar o carro", "Estudar Python"]

def test_marcar_concluida():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o carro")
    tarefa1.marcar_concluida(0)
    assert "Lavar o carro" in tarefa1.concluidas
    assert len(tarefa1.tarefas) == 1

def test_marcar_concluida_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.marcar_concluida(2)

def test_listar_concluidas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o carro")
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.marcar_concluida(0)
    assert tarefa1.listar_concluidas() == ["Lavar o carro"]