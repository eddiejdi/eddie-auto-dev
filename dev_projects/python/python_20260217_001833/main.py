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

    def marcar_tarefa_concluida(self, index):
        if 0 <= index < len(self.tarefas):
            self.concluidas.append(self.tarefas.pop(index))
        else:
            raise IndexError("Índice inválido")

    def listar_concluidas(self):
        return self.concluidas

    def gerar_tarefa_randomica(self, quantidade):
        if not isinstance(quantidade, int) or quantidade <= 0:
            raise ValueError("Quantidade deve ser um número positivo inteiro")
        for _ in range(quantidade):
            self.adicionar_tarefa(f"Tarefa {random.randint(1, 100)}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.gerar_tarefa_randomica(5)
    print("Tarefas:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)

    print("\nConcluídas:")
    for tarefa in tarefa1.listar_concluidas():
        print(tarefa)