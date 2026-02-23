import pytest
from file_handler import FileHandler

def test_read_file_success():
    handler = FileHandler('test.txt')
    content = handler.read_file()
    assert content is not None
    assert 'Hello, World!' in content

def test_read_file_not_found():
    handler = FileHandler('nonexistent.txt')
    with pytest.raises(FileNotFoundError):
        handler.read_file()

def test_write_file_success():
    handler = FileHandler('test.txt')
    handler.write_file('Hello, World!')
    with open('test.txt', 'r') as file:
        content = file.read()
    assert content == 'Hello, World!\n'

def test_write_file_division_by_zero():
    handler = FileHandler('test.txt')
    with pytest.raises(ValueError):
        handler.write_file(0)

def test_append_file_success():
    handler = FileHandler('test.txt')
    handler.append_file('Hello, ')
    with open('test.txt', 'r') as file:
        content = file.read()
    assert content == 'Hello, World!\n'

def test_append_file_division_by_zero():
    handler = FileHandler('test.txt')
    with pytest.raises(ValueError):
        handler.append_file(0)