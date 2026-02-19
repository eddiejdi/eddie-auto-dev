import pytest
from tarefa1 import Tarefa1

def test_add_item():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    assert "Item 1" in tarefa1.items

def test_remove_item():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    tarefa1.remove_item(0)
    assert "Item 1" not in tarefa1.items

def test_get_random_items():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    tarefa1.add_item("Item 2")
    tarefa1.get_random_items(2)
    assert len(tarefa1.random_items) == 2
    assert "Item 1" in tarefa1.random_items
    assert "Item 2" in tarefa1.random_items

def test_print_items():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    tarefa1.print_items()
    expected_output = ["Item 1"]
    assert tarefa1.items == expected_output

def test_print_random_items():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    tarefa1.add_item("Item 2")
    tarefa1.get_random_items(2)
    tarefa1.print_random_items()
    expected_output = ["Item 1", "Item 2"]
    assert tarefa1.random_items == expected_output

def test_add_item_invalid_type():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.add_item(123)

def test_remove_item_out_of_range():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    with pytest.raises(IndexError):
        tarefa1.remove_item(-1)
    with pytest.raises(IndexError):
        tarefa1.remove_item(len(tarefa1.items))

def test_get_random_items_invalid_count():
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    with pytest.raises(ValueError):
        tarefa1.get_random_items(0)
    with pytest.raises(ValueError):
        tarefa1.get_random_items(-1)

def test_print_items_empty_list():
    tarefa1 = Tarefa1()
    tarefa1.print_items()
    expected_output = []
    assert tarefa1.items == expected_output

def test_print_random_items_empty_list():
    tarefa1 = Tarefa1()
    tarefa1.get_random_items(2)
    tarefa1.print_random_items()
    expected_output = []
    assert tarefa1.random_items == expected_output