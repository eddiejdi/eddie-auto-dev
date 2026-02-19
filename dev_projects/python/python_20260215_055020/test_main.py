import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome

class Sprint:
    def __init__(self, tarefas):
        self.tarefas = tarefas

    def listar_tarefas(self):
        for tarefa in self.tarefas:
            print(tarefa.nome)

def main():
    # Criar uma lista de tarefas
    tarefas = [
        Tarefa("Implementar Tarefa 1"),
        Tarefa("Testar Tarefa 1"),
        Tarefa("Refatorar Tarefa 1")
    ]

    # Criar um sprint com as tarefas
    sprint = Sprint(tarefas)

    # Listar todas as tarefas do sprint
    sprint.listar_tarefas()

if __name__ == "__main__":
    main()