import os

class ScrumProject:
    def __init__(self, project_name):
        self.project_name = project_name
        self.tasks = []

    def add_task(self, task_name):
        task = Task(task_name)
        self.tasks.append(task)

    def remove_task(self, task_name):
        for task in self.tasks:
            if task.name == task_name:
                self.tasks.remove(task)
                break

    def list_tasks(self):
        for task in self.tasks:
            print(f"Task: {task.name}, Status: {task.status}")

class Task:
    def __init__(self, name):
        self.name = name
        self.status = "Pending"

    def update_status(self, new_status):
        if new_status in ["In Progress", "Completed"]:
            self.status = new_status
        else:
            raise ValueError("Invalid status. Please use 'In Progress' or 'Completed'.")

def main():
    project = ScrumProject("My Project")

    while True:
        print("\nScrum Project Management")
        print("1. Add Task")
        print("2. Remove Task")
        print("3. List Tasks")
        print("4. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            task_name = input("Enter task name: ")
            project.add_task(task_name)
            print(f"Task '{task_name}' added successfully.")
        elif choice == "2":
            task_name = input("Enter task name to remove: ")
            project.remove_task(task_name)
            print(f"Task '{task_name}' removed successfully.")
        elif choice == "3":
            project.list_tasks()
        elif choice == "4":
            print("Exiting the application. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()