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

    def remover_tarefa(self, index):
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[index]

    def salvar_tarefas(self, arquivo="tarefas.txt"):
        with open(arquivo, "w") as file:
            for tarefa in self.tarefas:
                file.write(f"{tarefa}\n")

    def carregar_tarefas(self, arquivo="tarefas.txt"):
        if not os.path.exists(arquivo):
            return
        with open(arquivo, "r") as file:
            self.tarefas = [linha.strip() for linha in file.readlines()]

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o café")
    tarefa1.adicionar_tarefa("Estudar Python")
    print(tarefa1.listar_tarefas())
    tarefa1.remover_tarefa(0)
    print(tarefa1.listar_tarefas())
    tarefa1.salvar_tarefas()
    tarefa1.carregar_tarefas()
    print(tarefa1.listar_tarefas())