import pytest

class Tarefa1:
    def __init__(self):
        self.task_list = []

    def add_task(self, task):
        if not isinstance(task, str):
            raise ValueError("Task must be a string")
        self.task_list.append(task)

    def remove_task(self, task):
        if task in self.task_list:
            self.task_list.remove(task)
        else:
            raise ValueError("Task not found")

    def list_tasks(self):
        return self.task_list

def test_add_task_success():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Fazer compras")
    assert "Fazer compras" in tarefa1.list_tasks()

def test_add_task_error_non_string():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.add_task(123)

def test_remove_task_success():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Fazer compras")
    tarefa1.remove_task("Fazer compras")
    assert len(tarefa1.list_tasks()) == 0

def test_remove_task_error_not_found():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remove_task("Estudar Python")

def test_list_tasks_success():
    tarefa1 = Tarefa1()
    tarefa1.add_task("Fazer compras")
    tarefa1.add_task("Estudar Python")
    assert tarefa1.list_tasks() == ["Fazer compras", "Estudar Python"]