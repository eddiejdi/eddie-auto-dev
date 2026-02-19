import pytest
from your_module import FileProcessor

def test_file_processor_read():
    # Teste para leitura de arquivo com sucesso
    processor = FileProcessor('example.txt')
    content = processor.read_file()
    assert content is not None
    assert "Sample text" in content

    # Teste para leitura de arquivo que não existe
    with pytest.raises(FileNotFoundError):
        processor = FileProcessor('nonexistent.txt')
        processor.read_file()

def test_file_processor_write():
    # Teste para escrita de arquivo com sucesso
    processor = FileProcessor('example.txt')
    content = "New content"
    processor.write_file(content)
    assert os.path.exists('example.txt') and open('example.txt').read() == content

    # Teste para escrita de arquivo com erro (divisão por zero)
    with pytest.raises(Exception):
        processor = FileProcessor('nonexistent.txt')
        processor.write_file(10 / 0)

def test_file_processor_edge_cases():
    # Teste para leitura de arquivo vazio
    processor = FileProcessor('empty.txt')
    content = processor.read_file()
    assert content is None

    # Teste para escrita de arquivo com string vazia
    processor = FileProcessor('empty.txt')
    processor.write_file("")
    assert os.path.exists('empty.txt') and open('empty.txt').read() == ""

    # Teste para escrita de arquivo com None
    processor = FileProcessor('none.txt')
    processor.write_file(None)
    assert os.path.exists('none.txt') and open('none.txt').read() == ""