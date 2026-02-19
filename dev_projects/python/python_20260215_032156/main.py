import os

class Tarefa1:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        if not isinstance(task, str):
            raise ValueError("Task must be a string")
        self.tasks.append(task)

    def remove_task(self, index):
        if not isinstance(index, int) or index < 0 or index >= len(self.tasks):
            raise IndexError("Index out of range")
        del self.tasks[index]

    def list_tasks(self):
        return self.tasks

    def save_tasks(self, filename):
        with open(filename, 'w') as file:
            for task in self.tasks:
                file.write(f"{task}\n")

    def load_tasks(self, filename):
        if not os.path.exists(filename):
            raise FileNotFoundError("File does not exist")
        with open(filename, 'r') as file:
            self.tasks = [line.strip() for line in file.readlines()]

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.add_task("Tarefa 1")
    tarefa1.add_task("Tarefa 2")
    print(tarefa1.list_tasks())
    tarefa1.save_tasks("tasks.txt")
    tarefa1.load_tasks("tasks.txt")
    print(tarefa1.list_tasks())