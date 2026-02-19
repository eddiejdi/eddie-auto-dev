import pytest
from tarefa1 import Tarefa1

def test_add_item():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso com valores válidos
    tarefa1.add_item("Item 1")
    assert len(tarefa1.items) == 1
    
    # Caso de erro (divisão por zero)
    with pytest.raises(ValueError):
        tarefa1.add_item(0)

def test_remove_item():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso
    tarefa1.add_item("Item 1")
    tarefa1.remove_item(0)
    assert len(tarefa1.items) == 0
    
    # Caso de erro (índice inválido)
    with pytest.raises(IndexError):
        tarefa1.remove_item(5)

def test_list_items():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso
    tarefa1.add_item("Item 1")
    tarefa1.add_item("Item 2")
    assert tarefa1.list_items() == ["Item 1", "Item 2"]

def test_main():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso com valores válidos
    tarefa1.add_item("Item 1")
    tarefa1.remove_item(0)
    assert len(tarefa1.items) == 0
    
    # Caso de erro (divisão por zero)
    with pytest.raises(ValueError):
        tarefa1.add_item(0)

def test_main_edge_cases():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso com valores limite
    tarefa1.add_item("Item 1")
    assert len(tarefa1.items) == 1
    
    # Caso de erro (valores inválidos)
    with pytest.raises(ValueError):
        tarefa1.add_item(0)

def test_main_edge_cases_string():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso com string vazia
    assert tarefa1.list_items() == []