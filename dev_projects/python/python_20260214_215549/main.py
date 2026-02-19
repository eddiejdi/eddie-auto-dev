import os

class FileProcessor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file_content = None

    def read_file(self):
        try:
            with open(self.file_path, 'r') as file:
                self.file_content = file.read()
        except FileNotFoundError:
            print(f"File not found: {self.file_path}")
            return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False
        return True

    def write_file(self, content):
        try:
            with open(self.file_path, 'w') as file:
                file.write(content)
        except IOError:
            print(f"Error writing to file: {self.file_path}")
            return False
        except Exception as e:
            print(f"Error writing to file: {e}")
            return False
        return True

    def append_file(self, content):
        try:
            with open(self.file_path, 'a') as file:
                file.write(content)
        except IOError:
            print(f"Error appending to file: {self.file_path}")
            return False
        except Exception as e:
            print(f"Error appending to file: {e}")
            return False
        return True

    def delete_file(self):
        try:
            os.remove(self.file_path)
        except FileNotFoundError:
            print(f"File not found: {self.file_path}")
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
        return True

if __name__ == "__main__":
    file_processor = FileProcessor('example.txt')

    if file_processor.read_file():
        print("File content:")
        print(file_processor.file_content)

    if file_processor.write_file("Hello, World!"):
        print("File written successfully.")

    if file_processor.append_file("\nThis is an appended line."):
        print("Appended line to the file.")

    if file_processor.delete_file():
        print("File deleted successfully.")