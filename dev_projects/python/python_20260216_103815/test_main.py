import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome

    def listar(self):
        return f"Tarefa: {self.nome}"

def main():
    tarefa1 = Tarefa("Tarefa 1")
    print(tarefa1.listar())

if __name__ == "__main__":
    main()

# Testes unitários
def test_tarefa_listar_sucesso():
    # Caso de sucesso com valores válidos
    tarefa = Tarefa("Tarefa 1")
    assert tarefa.listar() == "Tarefa: Tarefa 1"

def test_tarefa_listar_erro_divisao_zero():
    # Caso de erro (divisão por zero)
    with pytest.raises(ZeroDivisionError):
        tarefa = Tarefa("Divisão por zero")
        tarefa.listar()

def test_tarefa_listar_erro_valores_invalidos():
    # Caso de erro (valores inválidos)
    with pytest.raises(ValueError):
        tarefa = Tarefa("")
        tarefa.listar()

def test_tarefa_listar_edge_case_strings_vazias():
    # Edge case (strings vazias)
    tarefa = Tarefa(" ")
    assert tarefa.listar() == "Tarefa: "

def test_tarefa_listar_edge_case_none():
    # Edge case (None)
    with pytest.raises(TypeError):
        tarefa = None
        tarefa.listar()