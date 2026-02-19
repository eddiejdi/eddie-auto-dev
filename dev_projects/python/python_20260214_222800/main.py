# Importação de bibliotecas
import sys

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

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nTarefa 1 - Menu:")
        print("1. Adicionar Tarefa")
        print("2. Listar Tarefas")
        print("3. Remover Tarefa")
        print("4. Sair")

        try:
            opcao = int(input("Escolha uma opção: "))
        except ValueError:
            print("Opção inválida. Por favor, escolha novamente.")
            continue

        if opcao == 1:
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao == 2:
            print("Tarefas:")
            for i, tarefa in enumerate(tarefa1.listar_tarefas()):
                print(f"{i+1}. {tarefa}")
        elif opcao == 3:
            try:
                index = int(input("Digite o índice da tarefa a remover: "))
                tarefa1.remover_tarefa(index)
            except IndexError as e:
                print(e)
        elif opcao == 4:
            sys.exit(0)
        else:
            print("Opção inválida. Por favor, escolha novamente.")