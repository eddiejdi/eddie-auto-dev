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

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.add_task("Fazer compras")
    tarefa1.add_task("Estudar Python")
    print(tarefa1.list_tasks())
    tarefa1.remove_task("Estudar Python")
    print(tarefa1.list_tasks())