import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []
        self.concluidas = []

    def add_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def remove_tarefa(self, tarefa):
        if tarefa in self.tarefas:
            self.tarefas.remove(tarefa)
        else:
            raise ValueError("Tarefa não encontrada")

    def listar_tarefas(self):
        return self.tarefas

    def marcar_concluida(self, tarefa):
        if tarefa in self.tarefas:
            self.concluidas.append(tarefa)
            self.tarefas.remove(tarefa)
        else:
            raise ValueError("Tarefa não encontrada")

    def listar_concluidas(self):
        return self.concluidas

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nMenu:")
        print("1. Adicionar Tarefa")
        print("2. Remover Tarefa")
        print("3. Listar Tarefas")
        print("4. Marcar Tarefa Concluída")
        print("5. Listar Tarefas Concluidas")
        print("6. Sair")

        opcao = input("Escolha uma opção: ")

        try:
            if opcao == "1":
                tarefa = input("Digite a nova tarefa: ")
                tarefa1.add_tarefa(tarefa)
            elif opcao == "2":
                tarefa = input("Digite a tarefa a ser removida: ")
                tarefa1.remove_tarefa(tarefa)
            elif opcao == "3":
                print("Tarefas:")
                for tarefa in tarefa1.listar_tarefas():
                    print(f"- {tarefa}")
            elif opcao == "4":
                tarefa = input("Digite a tarefa a ser marcada como concluída: ")
                tarefa1.marcar_concluida(tarefa)
            elif opcao == "5":
                print("Tarefas Concluídas:")
                for tarefa in tarefa1.listar_concluidas():
                    print(f"- {tarefa}")
            elif opcao == "6":
                print("Saindo...")
                break
            else:
                raise ValueError("Opção inválida")
        except ValueError as e:
            print(e)