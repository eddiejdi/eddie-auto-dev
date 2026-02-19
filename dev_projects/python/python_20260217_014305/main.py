import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def add_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def remove_tarefa(self, tarefa):
        if tarefa in self.tarefas:
            self.tarefas.remove(tarefa)
        else:
            raise ValueError(f"Tarefa '{tarefa}' não encontrada")

    def listar_tarefas(self):
        return self.tarefas

    def sortear_tarefa(self):
        if not self.tarefas:
            raise ValueError("Não há tarefas para serem sorteadas")
        random.shuffle(self.tarefas)
        return self.tarefas[0]

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Fazer compras")
    tarefa1.add_tarefa("Levar ao cinema")
    tarefa1.add_tarefa("Estudar Python")

    print("Tarefas:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)

    sorteada = tarefa1.sortear_tarefa()
    print(f"Sorteada: {sorteada}")