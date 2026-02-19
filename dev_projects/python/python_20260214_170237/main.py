import random

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
        if not isinstance(index, int) or index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[index]

    def embaralhar_tarefas(self):
        random.shuffle(self.tarefas)

    def salvar_tarefas(self, arquivo):
        with open(arquivo, 'w') as file:
            for tarefa in self.tarefas:
                file.write(tarefa + '\n')

    def carregar_tarefas(self, arquivo):
        try:
            with open(arquivo, 'r') as file:
                self.tarefas = [linha.strip() for linha in file]
        except FileNotFoundError:
            pass

# Exemplo de uso
if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    print(tarefa1.listar_tarefas())
    tarefa1.remover_tarefa(0)
    print(tarefa1.listar_tarefas())
    tarefa1.embaralhar_tarefas()
    print(tarefa1.listar_tarefas())
    tarefa1.salvar_tarefas("tarefas.txt")
    tarefa1.carregar_tarefas("tarefas.txt")
    print(tarefa1.listar_tarefas())