import pytest
from unittest.mock import patch
from your_module import ScrumProject, Task

def test_add_task():
    project = ScrumProject("My Project")
    task_name = "Task 1"
    project.add_task(task_name)
    assert len(project.tasks) == 1
    assert project.tasks[0].name == task_name

def test_remove_task():
    project = ScrumProject("My Project")
    task_name = "Task 1"
    project.add_task(task_name)
    project.remove_task(task_name)
    assert len(project.tasks) == 0

def test_list_tasks():
    project = ScrumProject("My Project")
    task_name = "Task 1"
    project.add_task(task_name)
    expected_output = f"Task: {task_name}, Status: Pending\n"
    with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        project.list_tasks()
        assert mock_stdout.getvalue() == expected_output

def test_add_task_invalid_name():
    project = ScrumProject("My Project")
    with pytest.raises(ValueError):
        project.add_task("123")

def test_remove_task_nonexistent_task():
    project = ScrumProject("My Project")
    task_name = "Nonexistent Task"
    with pytest.raises(ValueError):
        project.remove_task(task_name)

def test_list_tasks_empty_project():
    project = ScrumProject("My Project")
    expected_output = ""
    with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        project.list_tasks()
        assert mock_stdout.getvalue() == expected_output

def test_add_task_division_by_zero():
    project = ScrumProject("My Project")
    with pytest.raises(ValueError):
        project.add_task("Task 1 / 0")

def test_remove_task_division_by_zero():
    project = ScrumProject("My Project")
    with pytest.raises(ValueError):
        project.remove_task("Task 1 / 0")

def test_list_tasks_division_by_zero():
    project = ScrumProject("My Project")
    with pytest.raises(ValueError):
        project.list_tasks()