import pytest
from tarefa1 import Tarefa1

def test_add_task():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Tarefa 1")
    assert tarefa1.list_tasks() == ["Tarefa 1"]

def test_remove_task():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Tarefa 1")
    tarefa1.add_task("Tarefa 2")
    tarefa1.remove_task(0)
    assert tarefa1.list_tasks() == ["Tarefa 2"]

def test_list_tasks():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Tarefa 1")
    tarefa1.add_task("Tarefa 2")
    assert tarefa1.list_tasks() == ["Tarefa 1", "Tarefa 2"]

def test_save_tasks():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Tarefa 1")
    tarefa1.save_tasks("tasks.txt")
    with open("tasks.txt", 'r') as file:
        assert file.read() == "Tarefa 1\n"

def test_load_tasks():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Tarefa 1")
    tarefa1.save_tasks("tasks.txt")
    tarefa1.load_tasks("tasks.txt")
    assert tarefa1.list_tasks() == ["Tarefa 1"]

def test_invalid_add_task_type():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.add_task(123)

def test_invalid_remove_task_index():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Tarefa 1")
    with pytest.raises(IndexError):
        tarefa1.remove_task(-1)