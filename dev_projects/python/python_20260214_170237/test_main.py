import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.tarefas

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert tarefa1.listar_tarefas() == ["Tarefa 1", "Tarefa 2"]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(0)
    assert "Tarefa 1" not in tarefa1.tarefas

def test_embaralhar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.embaralhar_tarefas()
    assert "Tarefa 1" in tarefa1.tarefas and "Tarefa 2" in tarefa1.tarefas

def test_salvar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.salvar_tarefas("tarefas.txt")
    assert "Tarefa 1" in open("tarefas.txt").read()

def test_carregar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.carregar_tarefas("tarefas.txt")
    assert "Tarefa 1" in tarefa1.tarefas