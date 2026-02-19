import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    assert "Fazer compras" in tarefa1.listar_tarefas()

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    assert tarefa1.listar_tarefas() == ["Fazer compras", "Estudar Python"]

def test_marcar_concluida():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.marcar_concluida(0)
    assert len(tarefa1.listar_concluidas()) == 1
    assert "Fazer compras" in tarefa1.listar_concluidas()

def test_marcar_concluida_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.marcar_concluida(2)

def test_listar_concluidas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.marcar_concluida(0)
    assert len(tarefa1.listar_concluidas()) == 1
    assert "Fazer compras" in tarefa1.listar_concluidas()

def test_marcar_concluida_string():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.marcar_concluida("2")

def test_marcar_concluida_none():
    tarefa1 = Tarefa1()
    with pytest.raises(TypeError):
        tarefa1.marcar_concluida(None)