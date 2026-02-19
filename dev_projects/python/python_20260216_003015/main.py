import os

class FileProcessor:
    def __init__(self, directory):
        self.directory = directory

    def list_files(self):
        try:
            files = [f for f in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, f))]
            return files
        except Exception as e:
            print(f"Error listing files: {e}")
            return []

    def create_file(self, filename, content):
        try:
            with open(os.path.join(self.directory, filename), 'w') as file:
                file.write(content)
            print(f"File '{filename}' created successfully.")
        except Exception as e:
            print(f"Error creating file: {e}")

    def read_file(self, filename):
        try:
            with open(os.path.join(self.directory, filename), 'r') as file:
                content = file.read()
            return content
        except FileNotFoundError:
            print(f"File '{filename}' not found.")
            return None
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

    def delete_file(self, filename):
        try:
            os.remove(os.path.join(self.directory, filename))
            print(f"File '{filename}' deleted successfully.")
        except FileNotFoundError:
            print(f"File '{filename}' not found.")
        except Exception as e:
            print(f"Error deleting file: {e}")

if __name__ == "__main__":
    processor = FileProcessor("path/to/your/directory")
    
    # List files
    print(processor.list_files())
    
    # Create a new file
    processor.create_file("example.txt", "Hello, World!")
    
    # Read the content of an existing file
    content = processor.read_file("example.txt")
    if content:
        print(content)
    
    # Delete the file
    processor.delete_file("example.txt")