import re

class Scrum:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        if not isinstance(task, str):
            raise ValueError("Task must be a string")
        self.tasks.append(task)

    def remove_task(self, index):
        if not isinstance(index, int) or index < 0 or index >= len(self.tasks):
            raise IndexError("Invalid task index")
        del self.tasks[index]

    def list_tasks(self):
        return self.tasks

    def save_tasks(self, filename):
        with open(filename, 'w') as file:
            for task in self.tasks:
                file.write(task + '\n')

    def load_tasks(self, filename):
        try:
            with open(filename, 'r') as file:
                tasks = file.readlines()
                for i, line in enumerate(tasks):
                    self.add_task(line.strip())
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    scrum = Scrum()

    while True:
        print("\nScrum Board")
        print("1. Add Task")
        print("2. Remove Task")
        print("3. List Tasks")
        print("4. Save Tasks")
        print("5. Load Tasks")
        print("6. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            task = input("Enter the task: ")
            scrum.add_task(task)
        elif choice == "2":
            index = int(input("Enter the task index to remove: "))
            scrum.remove_task(index)
        elif choice == "3":
            print("\nTasks:")
            for i, task in enumerate(scrum.list_tasks()):
                print(f"{i+1}. {task}")
        elif choice == "4":
            filename = input("Enter the filename to save tasks: ")
            scrum.save_tasks(filename)
        elif choice == "5":
            filename = input("Enter the filename to load tasks: ")
            scrum.load_tasks(filename)
        elif choice == "6":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")