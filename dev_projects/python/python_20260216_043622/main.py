import json

class Task:
    def __init__(self, id, title, details=None, completed=False):
        self.id = id
        self.title = title
        self.details = details
        self.completed = completed

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "details": self.details,
            "completed": self.completed
        }

class TaskManager:
    def __init__(self, filename="tasks.json"):
        self.filename = filename
        self.tasks = []
        self.load_tasks()

    def load_tasks(self):
        try:
            with open(self.filename, 'r') as file:
                data = json.load(file)
                for task_dict in data:
                    task = Task(**task_dict)
                    self.tasks.append(task)
        except FileNotFoundError:
            pass

    def save_tasks(self):
        tasks_dict = [task.to_dict() for task in self.tasks]
        with open(self.filename, 'w') as file:
            json.dump(tasks_dict, file, indent=4)

    def add_task(self, title, details=None):
        new_id = len(self.tasks) + 1
        new_task = Task(new_id, title, details)
        self.tasks.append(new_task)
        self.save_tasks()

    def list_tasks(self):
        return [task.title for task in self.tasks]

    def mark_task_as_completed(self, task_id):
        for task in self.tasks:
            if task.id == task_id and not task.completed:
                task.completed = True
                self.save_tasks()
                return True
        return False

if __name__ == "__main__":
    manager = TaskManager()

    while True:
        print("\n1. Adicionar Tarefa")
        print("2. Listar Tarefas")
        print("3. Marcar Tarefa como Concluída")
        print("4. Sair")

        choice = input("Escolha uma opção: ")

        if choice == "1":
            title = input("Digite o título da tarefa: ")
            details = input("Digite as detalhes (opcional): ")
            manager.add_task(title, details)
        elif choice == "2":
            print("\nTarefas:")
            for i, task in enumerate(manager.list_tasks(), start=1):
                print(f"{i}. {task}")
        elif choice == "3":
            task_id = int(input("Digite o ID da tarefa para marcar como concluída: "))
            if manager.mark_task_as_completed(task_id):
                print("Tarefa marcada como concluída.")
            else:
                print("Tarefa não encontrada ou já concluída.")
        elif choice == "4":
            print("Saindo...")
            break
        else:
            print("Opção inválida. Tente novamente.")