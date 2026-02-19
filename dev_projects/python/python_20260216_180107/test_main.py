import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome

    def __str__(self):
        return f"Tarefa: {self.nome}"

def main():
    try:
        tarefa1 = Tarefa("Tarefa 1")
        print(tarefa1)
        
        # Adicione mais funcionalidades conforme necessário
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    main()

# Testes unitários

def test_tarefa_init():
    tarefa = Tarefa("Tarefa 1")
    assert tarefa.nome == "Tarefa 1"

def test_tarefa_str():
    tarefa = Tarefa("Tarefa 1")
    assert str(tarefa) == "Tarefa: Tarefa 1"

# Casos de erro

def test_tarefa_init_invalido():
    with pytest.raises(ValueError):
        Tarefa(123)

def test_tarefa_str_invalido():
    with pytest.raises(TypeError):
        str(123)