# Importa bibliotecas necessárias
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
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[index]

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    while True:
        print("\nTAREFAS:")
        for i, tarefa in enumerate(tarefa1.listar_tarefas()):
            print(f"{i+1}. {tarefa}")

        opcao = input("Digite uma opção (a)dd, (l)istar, (r)emover ou (q)uit: ")

        if opcao == "a":
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao == "l":
            print("\nTAREFAS:")
            for i, tarefa in enumerate(tarefa1.listar_tarefas()):
                print(f"{i+1}. {tarefa}")
        elif opcao == "r":
            index = int(input("Digite o índice da tarefa a remover: ")) - 1
            try:
                tarefa1.remover_tarefa(index)
                print("Tarefa removida com sucesso!")
            except IndexError as e:
                print(e)
        elif opcao == "q":
            sys.exit()
        else:
            print("Opção inválida. Tente novamente.")