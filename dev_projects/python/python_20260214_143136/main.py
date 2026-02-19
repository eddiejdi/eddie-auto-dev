class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if not isinstance(tarefa, str):
                raise ValueError("A tarefa deve ser uma string")
            self.tarefas.append(tarefa)
            print(f"Tarefa '{tarefa}' adicionada com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar tarefa: {e}")

    def listar_tarefas(self):
        try:
            if not self.tarefas:
                print("Nenhuma tarefa encontrada.")
            else:
                for i, tarefa in enumerate(self.tarefas, start=1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(f"Erro ao listar tarefas: {e}")

    def remover_tarefa(self, indice):
        try:
            if not isinstance(indice, int) or indice < 1 or indice > len(self.tarefas):
                raise ValueError("Índice inválido")
            removed_task = self.tarefas.pop(indice - 1)
            print(f"Tarefa '{removed_task}' removida com sucesso.")
        except Exception as e:
            print(f"Erro ao remover tarefa: {e}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nMenu:")
        print("1. Adicionar tarefa")
        print("2. Listar tarefas")
        print("3. Remover tarefa")
        print("4. Sair")

        choice = input("Escolha uma opção: ")

        if choice == "1":
            tarefa1.adicionar_tarefa(input("Digite a tarefa: "))
        elif choice == "2":
            tarefa1.listar_tarefas()
        elif choice == "3":
            indice = int(input("Digite o índice da tarefa a ser removida: "))
            tarefa1.remover_tarefa(indice)
        elif choice == "4":
            print("Saindo do programa.")
            break
        else:
            print("Opção inválida. Tente novamente.")