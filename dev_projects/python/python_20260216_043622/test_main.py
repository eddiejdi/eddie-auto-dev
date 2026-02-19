import pytest
from task_manager import TaskManager

def test_add_task():
    manager = TaskManager()
    title = "Teste Tarefa"
    details = "Descrição do teste"
    manager.add_task(title, details)
    assert len(manager.tasks) == 1
    assert manager.tasks[0].title == title
    assert manager.tasks[0].details == details

def test_add_task_invalid_title():
    manager = TaskManager()
    title = ""
    details = "Descrição do teste"
    with pytest.raises(ValueError):
        manager.add_task(title, details)

def test_list_tasks():
    manager = TaskManager()
    title1 = "Tarefa 1"
    title2 = "Tarefa 2"
    details1 = "Desc 1"
    details2 = "Desc 2"
    task1 = Task(1, title1, details1)
    task2 = Task(2, title2, details2)
    manager.tasks.append(task1)
    manager.tasks.append(task2)
    assert manager.list_tasks() == [title1, title2]

def test_mark_task_as_completed():
    manager = TaskManager()
    title = "Teste Tarefa"
    details = "Descrição do teste"
    task = Task(1, title, details)
    manager.tasks.append(task)
    manager.mark_task_as_completed(1)
    assert task.completed