class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        # Verifica se a tarefa já existe
        if tarefa in self.tarefas:
            raise ValueError("Tarefa já existente")
        self.tarefas.append(tarefa)

    def remover_tarefa(self, tarefa):
        # Verifica se a tarefa existe
        if tarefa not in self.tarefas:
            raise ValueError("Tarefa não encontrada")
        self.tarefas.remove(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def salvar_tarefas(self, arquivo):
        with open(arquivo, 'w') as file:
            for tarefa in self.tarefas:
                file.write(f"{tarefa}\n")

    def carregar_tarefas(self, arquivo):
        try:
            with open(arquivo, 'r') as file:
                self.tarefas = [linha.strip() for linha in file]
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")

    print(tarefa1.listar_tarefas())  # Output: ['Tarefa 1', 'Tarefa 2']

    tarefa1.salvar_tarefas("tarefas.txt")

    tarefa1.carregar_tarefas("tarefas.txt")
    print(tarefa1.listar_tarefas())  # Output: ['Tarefa 1', 'Tarefa 2']