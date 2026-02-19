import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def completar_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
            print(f"Tarefa {indice + 1} completada.")
        else:
            print("Índice de tarefa inválido.")

    def gerar_tarefa_randomica(self, quantidade=5):
        for _ in range(quantidade):
            tarefa = f"Task {random.randint(1, 100)}"
            self.adicionar_tarefa(tarefa)

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.gerar_tarefa_randomica()

    print("Tarefas geradas:")
    for indice, tarefa in enumerate(tarefa1.listar_tarefas(), start=1):
        print(f"{indice}. {tarefa}")

    while True:
        try:
            indice = int(input("Digite o índice da tarefa que deseja completar (ou -1 para sair): "))
            if indice == -1:
                break
            tarefa1.completar_tarefa(indice - 1)
        except ValueError:
            print("Índice inválido. Digite um número inteiro.")