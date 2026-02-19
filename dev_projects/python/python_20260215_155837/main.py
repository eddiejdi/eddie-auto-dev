import os

class FileProcessor:
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
            print("File written successfully")
        except Exception as e:
            print(f"An error occurred: {e}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <file_path> <action>")
        return

    file_path = sys.argv[1]
    action = sys.argv[2]

    processor = FileProcessor(file_path)

    if action == 'read':
        content = processor.read_file()
        if content is not None:
            print(content)
    elif action == 'write':
        content = input("Enter the content to write: ")
        processor.write_file(content)
    else:
        print(f"Invalid action: {action}")

if __name__ == "__main__":
    main()