import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if isinstance(tarefa, str):
                self.tarefas.append(tarefa)
                print(f"Tarefa '{tarefa}' adicionada com sucesso.")
            else:
                raise ValueError("A tarefa deve ser uma string.")
        except Exception as e:
            print(f"Erro ao adicionar tarefa: {e}")

    def listar_tarefas(self):
        try:
            if self.tarefas:
                print("Tarefas:")
                for i, tarefa in enumerate(self.tarefas, 1):
                    print(f"{i}. {tarefa}")
            else:
                print("Nenhuma tarefa adicionada.")
        except Exception as e:
            print(f"Erro ao listar tarefas: {e}")

    def remover_tarefa(self, posicao):
        try:
            if 1 <= posicao <= len(self.tarefas):
                removed_task = self.tarefas.pop(posicao - 1)
                print(f"Tarefa '{removed_task}' removida com sucesso.")
            else:
                raise ValueError("Posição inválida para remover tarefa.")
        except Exception as e:
            print(f"Erro ao remover tarefa: {e}")

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert len(tarefa1.tarefas) == 1
    assert tarefa1.tarefas[0] == "Tarefa 1"

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.listar_tarefas()
    assert "Tarefa 1" in tarefa1.tarefas
    assert "Tarefa 2" in tarefa1.tarefas

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    tarefa1.listar_tarefas()

def test_remover_tarefa_posicao_valida():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(2)
    assert len(tarefa1.tarefas) == 1
    assert tarefa1.tarefas[0] == "Tarefa 1"

def test_remover_tarefa_posicao_invalida():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(3)

def test_remover_tarefa_posicao_zero():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(0)