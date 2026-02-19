class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)
        print(f"Tarefa '{tarefa}' adicionada com sucesso.")

    def listar_tarefas(self):
        if not self.tarefas:
            print("Nenhuma tarefa disponível.")
        else:
            print("Tarefas disponíveis:")
            for i, tarefa in enumerate(self.tarefas, start=1):
                print(f"{i}. {tarefa}")

    def remover_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            removida = self.tarefas.pop(indice)
            print(f"Tarefa '{removida}' removida com sucesso.")
        else:
            print("Índice inválido.")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nMenu:")
        print("1. Adicionar Tarefa")
        print("2. Listar Tarefas")
        print("3. Remover Tarefa")
        print("4. Sair")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            tarefa = input("Digite a tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao == "2":
            tarefa1.listar_tarefas()
        elif opcao == "3":
            indice = int(input("Digite o índice da tarefa a remover: "))
            tarefa1.remover_tarefa(indice)
        elif opcao == "4":
            print("Saindo do programa.")
            break
        else:
            print("Opção inválida. Tente novamente.")