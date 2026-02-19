import pytest
from unittest.mock import patch, MagicMock

class Scrum:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        if not isinstance(task, str):
            raise ValueError("Task must be a string")
        self.tasks.append(task)

    def remove_task(self, index):
        if not isinstance(index, int) or index < 0 or index >= len(self.tasks):
            raise IndexError("Invalid task index")
        del self.tasks[index]

    def list_tasks(self):
        return self.tasks

    def save_tasks(self, filename):
        with open(filename, 'w') as file:
            for task in self.tasks:
                file.write(task + '\n')

    def load_tasks(self, filename):
        try:
            with open(filename, 'r') as file:
                tasks = file.readlines()
                for i, line in enumerate(tasks):
                    self.add_task(line.strip())
        except FileNotFoundError:
            pass

def test_add_task():
    scrum = Scrum()
    task = "Complete the project"
    scrum.add_task(task)
    assert task in scrum.tasks

def test_remove_task():
    scrum = Scrum()
    task = "Complete the project"
    scrum.add_task(task)
    scrum.remove_task(0)
    assert task not in scrum.tasks

def test_list_tasks():
    scrum = Scrum()
    tasks = ["Task 1", "Task 2"]
    for task in tasks:
        scrum.add_task(task)
    assert scrum.list_tasks() == tasks

def test_save_tasks():
    scrum = Scrum()
    filename = "test.txt"
    tasks = ["Task 1", "Task 2"]
    for task in tasks:
        scrum.add_task(task)
    scrum.save_tasks(filename)
    with open(filename, 'r') as file:
        saved_tasks = file.readlines()
        assert saved_tasks == ['Task 1\n', 'Task 2\n']

def test_load_tasks():
    scrum = Scrum()
    filename = "test.txt"
    tasks = ["Task 1", "Task 2"]
    for task in tasks:
        scrum.add_task(task)
    scrum.save_tasks(filename)
    scrum.load_tasks(filename)
    assert scrum.list_tasks() == tasks

def test_add_task_invalid_type():
    scrum = Scrum()
    with pytest.raises(ValueError):
        scrum.add_task(123)

def test_remove_task_index_out_of_range():
    scrum = Scrum()
    task = "Complete the project"
    scrum.add_task(task)
    with pytest.raises(IndexError):
        scrum.remove_task(len(scrum.tasks))

def test_list_tasks_empty():
    scrum = Scrum()
    assert scrum.list_tasks() == []

def test_save_tasks_file_not_found():
    scrum = Scrum()
    filename = "test.txt"
    with pytest.raises(FileNotFoundError):
        scrum.save_tasks(filename)

def test_load_tasks_file_not_found():
    scrum = Scrum()
    filename = "test.txt"
    with pytest.raises(FileNotFoundError):
        scrum.load_tasks(filename)