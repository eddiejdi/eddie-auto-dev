import os

class FileProcessor:
    def __init__(self, directory):
        self.directory = directory

    def list_files(self):
        try:
            return os.listdir(self.directory)
        except FileNotFoundError:
            print(f"Directory {self.directory} not found.")
            return []

    def create_file(self, file_name, content):
        try:
            with open(os.path.join(self.directory, file_name), 'w') as file:
                file.write(content)
            print(f"File '{file_name}' created successfully.")
        except Exception as e:
            print(f"Error creating file: {e}")

    def read_file(self, file_name):
        try:
            with open(os.path.join(self.directory, file_name), 'r') as file:
                return file.read()
        except FileNotFoundError:
            print(f"File '{file_name}' not found.")
            return None
        except Exception as e:
            print(f"Error reading file: {e}")

    def delete_file(self, file_name):
        try:
            os.remove(os.path.join(self.directory, file_name))
            print(f"File '{file_name}' deleted successfully.")
        except FileNotFoundError:
            print(f"File '{file_name}' not found.")
        except Exception as e:
            print(f"Error deleting file: {e}")

if __name__ == "__main__":
    directory = "example_directory"
    
    # Create a FileProcessor instance
    processor = FileProcessor(directory)
    
    # List files in the directory
    print("Files in the directory:")
    for file in processor.list_files():
        print(file)
    
    # Create a new file
    content = "Hello, World!"
    processor.create_file("example.txt", content)
    
    # Read the created file
    print("\nContent of 'example.txt':")
    print(processor.read_file("example.txt"))
    
    # Delete the created file
    processor.delete_file("example.txt")