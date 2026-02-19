import pytest

class Tarefa1:
    def __init__(self):
        self.items = []

    def add_item(self, item):
        if not isinstance(item, str):
            raise ValueError("Item deve ser uma string")
        self.items.append(item)

    def remove_item(self, index):
        if index < 0 or index >= len(self.items):
            raise IndexError("Índice inválido")
        del self.items[index]

    def list_items(self):
        return self.items

def test_add_item():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Tarefa 1")
    assert tarefa1.list_items() == ["Tarefa 1"]

def test_add_item_invalid_type():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.add_item(123)

def test_remove_item():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Tarefa 1")
    tarefa1.add_item("Tarefa 2")
    tarefa1.remove_item(0)
    assert tarefa1.list_items() == ["Tarefa 2"]

def test_remove_item_out_of_range():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remove_item(-1)

def test_list_items_empty():
    tarefa1 = Tarefa1()
    assert tarefa1.list_items() == []

def test_list_items_single_item():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Tarefa 1")
    assert tarefa1.list_items() == ["Tarefa 1"]

def test_list_items_multiple_items():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Tarefa 1")
    tarefa1.add_item("Tarefa 2")
    assert tarefa1.list_items() == ["Tarefa 1", "Tarefa 2"]