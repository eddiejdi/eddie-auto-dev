import argparse

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

def main():
    parser = argparse.ArgumentParser(description="Scrum Project Management Tool")
    subparsers = parser.add_subparsers(dest="command")

    # Add Task Command
    add_task_parser = subparsers.add_parser("add", help="Add a new task to the project")
    add_task_parser.add_argument("task_name", type=str, help="Name of the task")
    add_task_parser.set_defaults(func=add_task)

    # Remove Task Command
    remove_task_parser = subparsers.add_parser("remove", help="Remove an existing task from the project")
    remove_task_parser.add_argument("task_name", type=str, help="Name of the task to remove")
    remove_task_parser.set_defaults(func=remove_task)

    # List Tasks Command
    list_tasks_parser = subparsers.add_parser("list", help="List all tasks in the project")
    list_tasks_parser.set_defaults(func=list_tasks)

    args = parser.parse_args()

    try:
        if hasattr(args, "func"):
            args.func(args)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()