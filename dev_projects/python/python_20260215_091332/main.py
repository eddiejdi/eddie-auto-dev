# Importações necessárias
import os

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, tarefa):
        if tarefa in self.tarefas:
            self.tarefas.remove(tarefa)
        else:
            raise ValueError("Tarefa não encontrada")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    try:
        tarefa1.adicionar_tarefa("Entender o que é Python")
        tarefa1.adicionar_tarefa(20)  # Este deve lançar um erro
        print(tarefa1.listar_tarefas())
        tarefa1.remover_tarefa("Entender o que é Python")
    except ValueError as e:
        print(e)