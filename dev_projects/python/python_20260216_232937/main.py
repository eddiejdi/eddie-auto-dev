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

    def remover_tarefa(self, tarefa):
        if tarefa in self.tarefas:
            self.tarefas.remove(tarefa)
        else:
            raise ValueError("Tarefa não encontrada")

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Estudar Python")
    print("Lista de tarefas:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)
    tarefa1.remover_tarefa("Estudar Python")
    print("\nTarefas após remoção:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)