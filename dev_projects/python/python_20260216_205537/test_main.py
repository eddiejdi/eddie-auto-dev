import pytest
from unittest.mock import patch, call

class ScrumProject:
    def __init__(self):
        self.tasks = []

    def add_task(self, task_name):
        self.tasks.append(task_name)

    def remove_task(self, task_name):
        if task_name in self.tasks:
            self.tasks.remove(task_name)
        else:
            print(f"Task '{task_name}' not found.")

    def list_tasks(self):
        if not self.tasks:
            print("No tasks to display.")
        else:
            for i, task in enumerate(self.tasks, start=1):
                print(f"{i}. {task}")

def test_add_task(scrum_project):
    scrum_project.add_task("Task 1")
    assert scrum_project.tasks == ["Task 1"]

def test_remove_task(scrum_project):
    scrum_project.add_task("Task 1")
    scrum_project.remove_task("Task 1")
    assert scrum_project.tasks == []

def test_list_tasks_empty(scrum_project):
    scrum_project.list_tasks()
    assert "No tasks to display." in scrum_project.output

def test_list_tasks_with_tasks(scrum_project):
    scrum_project.add_task("Task 1")
    scrum_project.add_task("Task 2")
    scrum_project.list_tasks()
    assert "1. Task 1" in scrum_project.output
    assert "2. Task 2" in scrum_project.output

def test_remove_nonexistent_task(scrum_project):
    scrum_project.remove_task("Nonexistent Task")
    assert "Task 'Nonexistent Task' not found." in scrum_project.output