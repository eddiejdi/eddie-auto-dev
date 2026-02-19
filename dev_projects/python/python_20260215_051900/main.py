import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if isinstance(tarefa, str):
            self.tarefas.append(tarefa)
        else:
            raise ValueError("Tarefa deve ser uma string")

    def remover_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

    def listar_tarefas(self):
        return self.tarefas

    def gerar_tarefa_aleatoria(self):
        tarefa = f"Tarefa aleatória {random.randint(1, 100)}"
        self.adicionar_tarefa(tarefa)
        return tarefa

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    
    # Adicionando tarefas
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    
    # Listando tarefas
    print("Lista de tarefas:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)
    
    # Gerando tarefa aleatória
    nova_tarefa = tarefa1.gerar_tarefa_aleatoria()
    print(f"Nova tarefa gerada: {nova_tarefa}")
    
    # Removendo tarefa
    tarefa1.remover_tarefa(0)
    print("Lista de tarefas após remoção:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)