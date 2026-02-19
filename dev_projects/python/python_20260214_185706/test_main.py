import pytest

class ScrumTeam:
    def __init__(self):
        self.tasks = []

    def add_task(self, task: str):
        if not isinstance(task, str):
            raise ValueError("Task must be a string")
        self.tasks.append(task)

    def complete_task(self, index: int):
        if index < 0 or index >= len(self.tasks):
            raise IndexError("Index out of range")
        del self.tasks[index]

    def list_tasks(self) -> List[str]:
        return self.tasks

def test_add_task():
    team = ScrumTeam()
    team.add_task("Implement Tarefa 1")
    assert team.list_tasks() == ["Implement Tarefa 1"]

def test_complete_task():
    team = ScrumTeam()
    team.add_task("Testar Tarefa 1")
    team.complete_task(0)
    assert team.list_tasks() == ["Testar Tarefa 1"]

def test_list_tasks():
    team = ScrumTeam()
    team.add_task("Implement Tarefa 1")
    team.add_task("Testar Tarefa 1")
    assert team.list_tasks() == ["Implement Tarefa 1", "Testar Tarefa 1"]

def test_add_task_invalid_type():
    team = ScrumTeam()
    with pytest.raises(ValueError):
        team.add_task(123)

def test_complete_task_out_of_range():
    team = ScrumTeam()
    team.add_task("Testar Tarefa 1")
    with pytest.raises(IndexError):
        team.complete_task(-1)
    with pytest.raises(IndexError):
        team.complete_task(len(team.tasks))

def test_list_tasks_empty():
    team = ScrumTeam()
    assert team.list_tasks() == []