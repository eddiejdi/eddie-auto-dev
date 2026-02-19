import pytest
from src.tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    assert "Fazer compras" in tarefa1.listar_tarefas()

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para o banco")
    assert "Fazer compras" in tarefa1.listar_tarefas() and "Levar dinheiro para o banco" in tarefa1.listar_tarefas()

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert len(tarefa1.listar_tarefas()) == 0

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para o banco")
    tarefa1.remover_tarefa(0)
    assert "Levar dinheiro para o banco" in tarefa1.listar_tarefas()

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(-1)

def test_salvar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para o banco")
    tarefa1.salvar_tarefas("tarefas.txt")
    with open("tarefas.txt", 'r') as file:
        assert "Fazer compras\n" in file.read() and "Levar dinheiro para o banco\n" in file.read()

def test_salvar_tarefas_arquivo_inexistente():
    tarefa1 = Tarefa1()
    with pytest.raises(IOError):
        tarefa1.salvar_tarefas("tarefas.txt")

def test_carregar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para o banco")
    tarefa1.salvar_tarefas("tarefas.txt")
    carregada = Tarefa1()
    carregada.carregar_tarefas("tarefas.txt")
    assert "Fazer compras" in carregada.listar_tarefas() and "Levar dinheiro para o banco" in carregada.listar_tarefas()

def test_carregar_tarefas_arquivo_inexistente():
    tarefa1 = Tarefa1()
    with pytest.raises(IOError):
        carregada = Tarefa1()
        carregada.carregar_tarefas("tarefas.txt")