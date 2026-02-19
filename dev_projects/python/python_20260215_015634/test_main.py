import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if isinstance(tarefa, str):
                self.tarefas.append(tarefa)
                return f"Tarefa '{tarefa}' adicionada com sucesso."
            else:
                raise ValueError("A tarefa deve ser uma string.")
        except Exception as e:
            return f"Erro: {e}"

    def listar_tarefas(self):
        try:
            if self.tarefas:
                return "\n".join(self.tarefas)
            else:
                return "Não há tarefas adicionadas."
        except Exception as e:
            return f"Erro: {e}"

    def remover_tarefa(self, index):
        try:
            if 0 <= index < len(self.tarefas):
                removed_task = self.tarefas.pop(index)
                return f"Tarefa '{removed_task}' removida com sucesso."
            else:
                raise IndexError("Índice inválido.")
        except Exception as e:
            return f"Erro: {e}"

    def buscar_tarefa(self, tarefa):
        try:
            if isinstance(tarefa, str):
                for index, task in enumerate(self.tarefas):
                    if task == tarefa:
                        return f"Tarefa '{tarefa}' encontrada na posição {index}."
                return "Tarefa não encontrada."
            else:
                raise ValueError("A tarefa deve ser uma string.")
        except Exception as e:
            return f"Erro: {e}"

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    assert tarefa1.adicionar_tarefa("Fazer compras") == "Tarefa 'Fazer compras' adicionada com sucesso."
    assert tarefa1.adicionar_tarefa(123) == "Erro: A tarefa deve ser uma string."

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para a loja")
    assert tarefa1.listar_tarefas() == "Fazer compras\nLevar dinheiro para a loja"

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para a loja")
    assert tarefa1.remover_tarefa(0) == "Tarefa 'Fazer compras' removida com sucesso."
    assert tarefa1.listar_tarefas() == "Levar dinheiro para a loja"

def test_buscar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para a loja")
    assert tarefa1.buscar_tarefa("Fazer compras") == "Tarefa 'Fazer compras' encontrada na posição 0."
    assert tarefa1.buscar_tarefa("Outra tarefa") == "Tarefa não encontrada."

def test_adicionar_tarefa_string_vazia():
    tarefa1 = Tarefa1()
    assert tarefa1.adicionar_tarefa("") == "Erro: A tarefa deve ser uma string."

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    assert tarefa1.remover_tarefa(0) == "Erro: Índice inválido."