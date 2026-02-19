import random

class Tarefa1:
    def __init__(self):
        self.tarefas = [
            "Tarefa 1",
            "Tarefa 2",
            "Tarefa 3",
            # Adicione mais tarefas conforme necessário
        ]

    def selecionar_tarefa(self):
        return random.choice(self.tarefas)

if __name__ == "__main__":
    tarefa = Tarefa1()
    print(f"Tarefa selecionada: {tarefa.selecionar_tarefa()}")