import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []
        self.concluidas = []

    def adicionar_tarefa(self, tarefa):
        if isinstance(tarefa, str):
            self.tarefas.append(tarefa)
        else:
            raise ValueError("Tarefa deve ser uma string")

    def listar_tarefas(self):
        return self.tarefas

    def concluir_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            tarefa = self.tarefas.pop(index)
            self.concluidas.append(tarefa)
            print(f"Tarefa concluída: {tarefa}")
        else:
            raise IndexError("Índice de tarefa inválido")

    def listar_concluidas(self):
        return self.concluidas

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.adicionar_tarefa("Lavar o carro")
    print("Tarefas:")
    for i, tarefa in enumerate(tarefa1.listar_tarefas()):
        print(f"{i+1}. {tarefa}")
    tarefa1.concluir_tarefa(0)
    print("\nConcluídas:")
    for i, tarefa in enumerate(tarefa1.listar_concluidas()):
        print(f"{i+1}. {tarefa}")