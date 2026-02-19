import pytest
from tarefa1 import Tarefa1

def test_adicionar_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    assert "Item 1" in tarefa1.items, "Item não foi adicionado corretamente."

def test_remover_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.remover_item("Item 1")
    assert len(tarefa1.items) == 0, "Item não foi removido corretamente."

def test_listar_itens():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.adicionar_item("Item 2")
    tarefa1.listar_itens()
    assert "Item 1" in tarefa1.items and "Item 2" in tarefa1.items, "Itens não foram listados corretamente."

def test_buscar_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.buscar_item("Item 1")
    assert "Item 1" in tarefa1.items, "Item não foi encontrado corretamente."