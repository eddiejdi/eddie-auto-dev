import pytest
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

def test_list_files_successfully():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # List files in the directory
    assert processor.list_files() == [], f"Expected empty list, got {processor.list_files()}"

def test_list_files_error():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # List files in the directory
    with pytest.raises(FileNotFoundError):
        assert processor.list_files() == [], f"Expected empty list, got {processor.list_files()}"

def test_create_file_successfully():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    file_name = "test.txt"
    content = "Hello, World!"
    
    # Create the file
    processor.create_file(file_name, content)
    
    # Read the created file
    assert processor.read_file(file_name) == content, f"Expected content '{content}', got {processor.read_file(file_name)}"

def test_create_file_error():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    file_name = "test.txt"
    content = "Hello, World!"
    
    # Create the file
    with pytest.raises(Exception):
        processor.create_file(file_name, content)

def test_read_file_successfully():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    file_name = "test.txt"
    content = "Hello, World!"
    
    # Create the file
    processor.create_file(file_name, content)
    
    # Read the created file
    assert processor.read_file(file_name) == content, f"Expected content '{content}', got {processor.read_file(file_name)}"

def test_read_file_error():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    file_name = "test.txt"
    content = "Hello, World!"
    
    # Create the file
    processor.create_file(file_name, content)
    
    with pytest.raises(FileNotFoundError):
        assert processor.read_file("nonexistent.txt") == None, f"Expected None, got {processor.read_file('nonexistent.txt')}"

def test_delete_file_successfully():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    file_name = "test.txt"
    content = "Hello, World!"
    
    # Create the file
    processor.create_file(file_name, content)
    
    # Delete the file
    processor.delete_file(file_name)
    
    # Check if the file is deleted
    assert not os.path.exists(os.path.join(directory, file_name)), f"File '{file_name}' should be deleted."

def test_delete_file_error():
    directory = "example_directory"
    processor = FileProcessor(directory)
    
    # Create a new directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    file_name = "test.txt"
    content = "Hello, World!"
    
    # Create the file
    processor.create_file(file_name, content)
    
    with pytest.raises(FileNotFoundError):
        processor.delete_file("nonexistent.txt")