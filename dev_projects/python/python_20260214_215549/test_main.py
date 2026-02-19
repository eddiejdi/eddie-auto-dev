import pytest
from your_module import FileProcessor

def test_read_file():
    file_processor = FileProcessor('example.txt')
    assert file_processor.read_file() is True

def test_write_file():
    file_processor = FileProcessor('example.txt')
    assert file_processor.write_file("Hello, World!") is True

def test_append_file():
    file_processor = FileProcessor('example.txt')
    assert file_processor.append_file("\nThis is an appended line.") is True

def test_delete_file():
    file_processor = FileProcessor('example.txt')
    assert file_processor.delete_file() is True