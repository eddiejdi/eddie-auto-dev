import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert tarefa1.listar_tarefas() == ["Tarefa 1"]

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
    assert tarefa1.listar_tarefas() == ["Tarefa 2"]

def test_salvar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.salvar_tarefas("tarefas.txt")
    with open("tarefas.txt", 'r') as file:
        assert file.read() == "Tarefa 1\n"

def test_carregar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.salvar_tarefas("tarefas.txt")
    tarefa1.carregar_tarefas("tarefas.txt")
    assert tarefa1.listar_tarefas() == ["Tarefa 1"]

def test_adicionar_tarefa_invalida():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert tarefa1.listar_tarefas() == []

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(0)

def test_salvar_tarefas_arquivo_nao_existe():
    tarefa1 = Tarefa1()
    with pytest.raises(FileNotFoundError):
        tarefa1.salvar_tarefas("tarefas.txt")

def test_carregar_tarefas_arquivo_nao_existe():
    tarefa1 = Tarefa1()
    with pytest.raises(FileNotFoundError):
        tarefa1.carregar_tarefas("tarefas.txt")