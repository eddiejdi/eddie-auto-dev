import pytest
from tarefa1 import Tarefa1

def test_adicionar_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    assert "Item 1" in tarefa1.listar_itens()

def test_remover_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.remover_item(0)
    assert len(tarefa1.listar_itens()) == 0

def test_listar_itens():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.adicionar_item("Item 2")
    assert tarefa1.listar_itens() == ["Item 1", "Item 2"]

def test_salvar_itens():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.salvar_itens("tarefas.txt")
    with open("tarefas.txt", 'r') as file:
        content = file.read()
    assert "Item 1" in content

def test_carregar_itens():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.salvar_itens("tarefas.txt")
    tarefa1.carregar_itens("tarefas.txt")
    assert len(tarefa1.listar_itens()) == 1

def test_divisao_por_zero():
    with pytest.raises(ValueError):
        Tarefa1().dividir(10, 0)

def test_valores_invalidos():
    with pytest.raises(ValueError):
        Tarefa1().adicionar_item(None)
    with pytest.raises(ValueError):
        Tarefa1().remover_item(-1)

def test_edge_cases():
    tarefa1 = Tarefa1()
    assert len(tarefa1.listar_itens()) == 0
    tarefa1.carregar_itens("tarefas.txt")
    assert len(tarefa1.listar_itens()) == 0