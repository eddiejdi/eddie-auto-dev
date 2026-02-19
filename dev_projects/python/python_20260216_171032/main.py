import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
        else:
            print("Índice inválido")

    def gerar_numeros_aleatorios(self, quantidade):
        try:
            return random.sample(range(1, 101), quantidade)
        except ValueError as e:
            print(f"Erro: {e}")
            return []

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.listar_tarefas()

    indice_remover = int(input("Digite o índice da tarefa a remover: "))
    tarefa1.remover_tarefa(indice_remover)

    quantidade_numeros = int(input("Digite a quantidade de números aleatórios a gerar: "))
    numeros_aleatorios = tarefa1.gerar_numeros_aleatorios(quantidade_numeros)
    print("Números aleatórios:", numeros_aleatorios)