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

    def editar_tarefa(self, index, nova_tarefa):
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        if not isinstance(nova_tarefa, str):
            raise ValueError("Nova tarefa deve ser uma string")
        self.tarefas[index] = nova_tarefa

    def __str__(self):
        return "\n".join(self.tarefas)

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    print(tarefa1)
    tarefa1.remover_tarefa(0)
    print(tarefa1)
    tarefa1.editar_tarefa(0, "Comprar pão")
    print(tarefa1)