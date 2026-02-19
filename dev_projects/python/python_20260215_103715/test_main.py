import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas: List[str] = []

    def adicionar_tarefa(self, tarefa: str) -> None:
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self) -> List[str]:
        return self.tarefas

    def remover_tarefa(self, index: int) -> None:
        if not isinstance(index, int):
            raise ValueError("Índice deve ser um inteiro")
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice fora do alcance da lista")
        del self.tarefas[index]

    def __str__(self) -> str:
        return f"Tarefa1(tarefas={self.tarefas})"

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert len(tarefa1.tarefas) == 1
    assert tarefa1.tarefas[0] == "Tarefa 1"

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert tarefa1.listar_tarefas() == ["Tarefa 1", "Tarefa 2"]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(0)
    assert len(tarefa1.tarefas) == 1
    assert tarefa1.tarefas[0] == "Tarefa 2"

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    assert len(tarefa1.listar_tarefas()) == 0

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(1)

def test_str():
    tarefa1 = Tarefa1()
    assert str(tarefa1) == "Tarefa1(tarefas=[])"