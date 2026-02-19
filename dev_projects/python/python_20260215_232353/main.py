class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, indice):
        if not isinstance(indice, int) or indice < 0 or indice >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[indice]

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Leitura")
    print(tarefa1.listar_tarefas())  # Output: ['Fazer compras', 'Leitura']
    tarefa1.remover_tarefa(0)
    print(tarefa1.listar_tarefas())  # Output: ['Leitura']