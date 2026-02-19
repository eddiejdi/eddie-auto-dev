import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []
        self.concluidas = []

    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def marcar_concluida(self, indice):
        if 0 <= indice < len(self.tarefas):
            self.concluidas.append(self.tarefas.pop(indice))
        else:
            raise IndexError("Índice inválido")

    def listar_concluidas(self):
        return self.concluidas

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o carro")
    tarefa1.adicionar_tarefa("Estudar Python")
    print(tarefa1.listar_tarefas())
    tarefa1.marcar_concluida(0)
    print(tarefa1.listar_concluidas())