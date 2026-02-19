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

    def remover_tarefa(self, indice):
        try:
            del self.tarefas[indice]
        except IndexError:
            raise ValueError("Índice inválido")

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    while True:
        print("\nTAREFAS")
        for i, tarefa in enumerate(tarefa1.listar_tarefas()):
            print(f"{i+1}. {tarefa}")

        opcao = input("Digite uma opção (a)dd, (l)istar, (r)emover ou (q)uit: ")

        if opcao.lower() == 'a':
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao.lower() == 'l':
            print("\nTAREFAS:")
            for i, tarefa in enumerate(tarefa1.listar_tarefas()):
                print(f"{i+1}. {tarefa}")
        elif opcao.lower() == 'r':
            indice = int(input("Digite o índice da tarefa a remover: ")) - 1
            tarefa1.remover_tarefa(indice)
        elif opcao.lower() == 'q':
            sys.exit()
        else:
            print("Opção inválida")