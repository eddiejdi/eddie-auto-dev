class Tarefa1:
    def __init__(self):
        self.task_id = None
        self.description = None

    @classmethod
    def create_task(cls, task_id, description):
        try:
            new_task = cls()
            new_task.task_id = task_id
            new_task.description = description
            return new_task
        except Exception as e:
            print(f"Error creating task: {e}")
            return None

    @classmethod
    def update_task(cls, task_id, new_description):
        try:
            updated_task = cls()
            updated_task.task_id = task_id
            updated_task.description = new_description
            return updated_task
        except Exception as e:
            print(f"Error updating task: {e}")
            return None

    @classmethod
    def delete_task(cls, task_id):
        try:
            # Simulando a remoção de uma tarefa no banco de dados
            print(f"Task with ID {task_id} deleted.")
            return True
        except Exception as e:
            print(f"Error deleting task: {e}")
            return False

    @classmethod
    def list_tasks(cls):
        try:
            # Simulando a lista de tarefas no banco de dados
            tasks = [
                {"id": 1, "description": "Implement Tarefa 1"},
                {"id": 2, "description": "Implement Tarefa 2"}
            ]
            return tasks
        except Exception as e:
            print(f"Error listing tasks: {e}")
            return []

    def __str__(self):
        return f"Task ID: {self.task_id}, Description: {self.description}"

if __name__ == "__main__":
    task1 = Tarefa1.create_task(1, "Implement Tarefa 1")
    print(task1)

    updated_task = Tarefa1.update_task(1, "Implement Tarefa 1 - Parte 2")
    print(updated_task)

    deleted_task = Tarefa1.delete_task(1)
    print(deleted_task)

    tasks = Tarefa1.list_tasks()
    for task in tasks:
        print(task)