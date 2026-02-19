import pytest
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

def test_list_files_success():
    processor = FileProcessor("path/to/your/directory")
    assert processor.list_files() == ['example.txt']

def test_create_file_success():
    processor = FileProcessor("path/to/your/directory")
    processor.create_file("test.txt", "Hello, World!")
    assert os.path.exists(os.path.join(processor.directory, "test.txt"))

def test_read_file_success():
    processor = FileProcessor("path/to/your/directory")
    processor.create_file("test.txt", "Hello, World!")
    content = processor.read_file("test.txt")
    assert content == "Hello, World!"

def test_delete_file_success():
    processor = FileProcessor("path/to/your/directory")
    processor.create_file("test.txt", "Hello, World!")
    processor.delete_file("test.txt")
    assert not os.path.exists(os.path.join(processor.directory, "test.txt"))

def test_list_files_error():
    processor = FileProcessor("nonexistent_directory")
    with pytest.raises(Exception):
        processor.list_files()

def test_create_file_error():
    processor = FileProcessor("path/to/your/directory")
    with pytest.raises(FileNotFoundError):
        processor.create_file("existing_file.txt", "Hello, World!")

def test_read_file_error():
    processor = FileProcessor("path/to/your/directory")
    processor.create_file("test.txt", "Hello, World!")
    with pytest.raises(FileNotFoundError):
        processor.read_file("nonexistent_file.txt")

def test_delete_file_error():
    processor = FileProcessor("path/to/your/directory")
    processor.create_file("test.txt", "Hello, World!")
    with pytest.raises(FileNotFoundError):
        processor.delete_file("nonexistent_file.txt")