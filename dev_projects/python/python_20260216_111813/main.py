class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    print(tarefa1.listar_tarefas())  # Output: ['Tarefa 1', 'Tarefa 2']
    tarefa1.remover_tarefa(0)
    print(tarefa1.listar_tarefas())  # Output: ['Tarefa 2']