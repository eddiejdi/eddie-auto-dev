import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    assert tarefa1.tarefas == ["Fazer compras"]

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar a casa")
    assert tarefa1.listar_tarefas() == ["Fazer compras", "Levar a casa"]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar a casa")
    tarefa1.remover_tarefa(0)
    assert tarefa1.listar_tarefas() == ["Levar a casa"]

def test_salvar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.salvar_tarefas()
    with open("tarefas.txt", "r") as file:
        assert file.read() == "Fazer compras\n"

def test_carregar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.salvar_tarefas()
    tarefa1.carregar_tarefas()
    assert tarefa1.listar_tarefas() == ["Fazer compras"]

def test_adicionar_tarefa_invalido():
    with pytest.raises(ValueError):
        Tarefa1().adicionar_tarefa(123)

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)