import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if not isinstance(tarefa, str):
                raise ValueError("A tarefa deve ser uma string")
            self.tarefas.append(tarefa)
            print(f"Tarefa '{tarefa}' adicionada com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar tarefa: {e}")

    def listar_tarefas(self):
        try:
            if not self.tarefas:
                print("Nenhuma tarefa encontrada.")
            else:
                for i, tarefa in enumerate(self.tarefas, start=1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(f"Erro ao listar tarefas: {e}")

    def remover_tarefa(self, indice):
        try:
            if not isinstance(indice, int) or indice < 1 or indice > len(self.tarefas):
                raise ValueError("Índice inválido")
            removed_task = self.tarefas.pop(indice - 1)
            print(f"Tarefa '{removed_task}' removida com sucesso.")
        except Exception as e:
            print(f"Erro ao remover tarefa: {e}")

def test_adicionar_tarefa_valido():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert len(tarefa1.tarefas) == 1

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    tarefa1.listar_tarefas()
    assert "Nenhuma tarefa encontrada." in capsys.readouterr().stdout

def test_listar_tarefas_com_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.listar_tarefas()
    assert "1. Tarefa 1" in capsys.readouterr().stdout
    assert "2. Tarefa 2" in capsys.readouterr().stdout

def test_remover_tarefa_valido():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.remover_tarefa(1)
    assert len(tarefa1.tarefas) == 0

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(3)

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(0)