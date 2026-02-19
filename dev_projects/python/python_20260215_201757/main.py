import os

class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password

class LoginManager:
    def __init__(self):
        self.users = {}

    def register(self, username, password):
        if username in self.users:
            raise ValueError("Username already exists")
        self.users[username] = User(username, password)

    def login(self, username, password):
        user = self.users.get(username)
        if not user or user.password != password:
            raise ValueError("Invalid username or password")
        return user

class CLI:
    def __init__(self, login_manager):
        self.login_manager = login_manager
        self.username = None
        self.password = None

    def start(self):
        while True:
            print("\n1. Register")
            print("2. Login")
            print("3. Exit")
            choice = input("Enter your choice: ")

            if choice == "1":
                username = input("Enter username: ")
                password = input("Enter password: ")
                self.login_manager.register(username, password)
                print(f"User {username} registered successfully.")
            elif choice == "2":
                if not self.username or not self.password:
                    print("Please login first.")
                    continue
                username = input("Enter username: ")
                password = input("Enter password: ")
                user = self.login_manager.login(username, password)
                print(f"Logged in as {user.username}.")
            elif choice == "3":
                break
            else:
                print("Invalid choice. Please try again.")

if __name__ == "__main__":
    login_manager = LoginManager()
    cli = CLI(login_manager)
    cli.start()