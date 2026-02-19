class Tarefa1:
    def __init__(self):
        self.task_list = []

    def add_task(self, task):
        try:
            self.task_list.append(task)
            print(f"Task '{task}' added successfully.")
        except Exception as e:
            print(f"Error adding task: {e}")

    def remove_task(self, task):
        try:
            if task in self.task_list:
                self.task_list.remove(task)
                print(f"Task '{task}' removed successfully.")
            else:
                print(f"Task '{task}' not found in the list.")
        except Exception as e:
            print(f"Error removing task: {e}")

    def list_tasks(self):
        try:
            if self.task_list:
                print("Tasks:")
                for i, task in enumerate(self.task_list, start=1):
                    print(f"{i}. {task}")
            else:
                print("No tasks available.")
        except Exception as e:
            print(f"Error listing tasks: {e}")

    def execute_task(self, index):
        try:
            if 0 <= index < len(self.task_list):
                task = self.task_list[index]
                print(f"Executing task '{task}'...")
                # Simulando a execução de uma tarefa
                import time
                time.sleep(2)
                print("Task executed successfully.")
            else:
                print("Invalid task index.")
        except Exception as e:
            print(f"Error executing task: {e}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nTarefa 1 Menu:")
        print("1. Add Task")
        print("2. Remove Task")
        print("3. List Tasks")
        print("4. Execute Task")
        print("5. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            task = input("Enter the task to add: ")
            tarefa1.add_task(task)
        elif choice == "2":
            task = input("Enter the task to remove: ")
            tarefa1.remove_task(task)
        elif choice == "3":
            tarefa1.list_tasks()
        elif choice == "4":
            index = int(input("Enter the index of the task to execute: "))
            tarefa1.execute_task(index)
        elif choice == "5":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")