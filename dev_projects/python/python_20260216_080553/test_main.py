import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, index):
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[index]

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Comprar leite")
    tarefa1.adicionar_tarefa("Estudar Python")
    print(tarefa1.listar_tarefas())
    tarefa1.remover_tarefa(0)
    print(tarefa1.listar_tarefas())

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Comprar leite")
    assert tarefa1.tarefas == ["Comprar leite"]

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Comprar leite")
    tarefa1.adicionar_tarefa("Estudar Python")
    assert tarefa1.listar_tarefas() == ["Comprar leite", "Estudar Python"]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Comprar leite")
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.remover_tarefa(0)
    assert tarefa1.listar_tarefas() == ["Estudar Python"]

def test_adicionar_tarefa_invalido():
    with pytest.raises(ValueError):
        Tarefa1().adicionar_tarefa(123)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert tarefa1.listar_tarefas() == []

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(0)

def test_adicionar_tarefa_string_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa("")

def test_remover_tarefa_string_vazia():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(0)