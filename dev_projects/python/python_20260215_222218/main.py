class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if isinstance(tarefa, str):
            self.tarefas.append(tarefa)
        else:
            raise ValueError("Tarefa deve ser uma string")

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar ao banco")
    print(tarefa1.listar_tarefas())
    tarefa1.remover_tarefa(0)
    print(tarefa1.listar_tarefas())