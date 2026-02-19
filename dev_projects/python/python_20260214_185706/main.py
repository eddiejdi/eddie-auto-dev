from typing import List

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

if __name__ == "__main__":
    team = ScrumTeam()
    team.add_task("Implement Tarefa 1")
    team.add_task("Testar Tarefa 1")
    print(team.list_tasks())  # Output: ['Implement Tarefa 1', 'Testar Tarefa 1']
    team.complete_task(0)
    print(team.list_tasks())  # Output: ['Testar Tarefa 1']