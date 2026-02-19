import os

class FileHandler:
    def __init__(self, file_path):
        self.file_path = file_path

    def read_file(self):
        try:
            with open(self.file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            print(f"File not found: {self.file_path}")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def write_file(self, content):
        try:
            with open(self.file_path, 'w') as file:
                file.write(content)
            print(f"File written successfully: {self.file_path}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def append_file(self, content):
        try:
            with open(self.file_path, 'a') as file:
                file.write(content + '\n')
            print(f"Content appended to file successfully: {self.file_path}")
        except Exception as e:
            print(f"An error occurred: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py [command] [file_path]")
        return

    command = sys.argv[1]
    file_path = sys.argv[2]

    handler = FileHandler(file_path)

    if command == 'read':
        content = handler.read_file()
        if content is not None:
            print(content)
    elif command == 'write':
        content = input("Enter the content to write: ")
        handler.write_file(content)
    elif command == 'append':
        content = input("Enter the content to append: ")
        handler.append_file(content)
    else:
        print(f"Invalid command: {command}")

if __name__ == "__main__":
    main()