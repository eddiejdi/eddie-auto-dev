import pytest
from datetime import datetime

class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password

class LoginSystem:
    def __init__(self):
        self.users = []
        self.current_user = None

    def register(self, username, password):
        new_user = User(username, password)
        self.users.append(new_user)
        print(f"User {username} registered successfully.")

    def login(self, username, password):
        for user in self.users:
            if user.username == username and user.password == password:
                self.current_user = user
                print("Login successful.")
                return True
        print("Invalid username or password.")
        return False

class UI:
    @staticmethod
    def display_menu():
        print("\nSCrum-1 Login System")
        print("1. Register")
        print("2. Login")
        print("3. Exit")

    @staticmethod
    def get_user_input(prompt):
        while True:
            try:
                return input(prompt)
            except ValueError:
                print("Invalid input. Please enter a valid option.")

    @staticmethod
    def main():
        login_system = LoginSystem()
        ui = UI()

        while True:
            ui.display_menu()
            choice = ui.get_user_input("Enter your choice: ")

            if choice == "1":
                username = ui.get_user_input("Enter your username: ")
                password = ui.get_user_input("Enter your password: ")
                login_system.register(username, password)
            elif choice == "2":
                username = ui.get_user_input("Enter your username: ")
                password = ui.get_user_input("Enter your password: ")
                if login_system.login(username, password):
                    print(f"Welcome, {username}!")
                    while True:
                        UI.display_menu()
                        user_choice = ui.get_user_input("Enter your choice: ")

                        if user_choice == "1":
                            # Implement functionality for creating a new task
                            pass
                        elif user_choice == "2":
                            # Implement functionality for viewing all tasks
                            pass
                        elif user_choice == "3":
                            print(f"Goodbye, {username}!")
                            break
            elif choice == "3":
                print("Exiting the program.")
                break
            else:
                print("Invalid option. Please try again.")

if __name__ == "__main__":
    UI.main()