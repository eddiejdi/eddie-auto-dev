class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if isinstance(tarefa, str):
                self.tarefas.append(tarefa)
                print(f"Tarefa '{tarefa}' adicionada com sucesso.")
            else:
                raise ValueError("A tarefa deve ser uma string.")
        except Exception as e:
            print(f"Erro ao adicionar tarefa: {e}")

    def listar_tarefas(self):
        try:
            if not self.tarefas:
                print("Nenhuma tarefa encontrada.")
            else:
                print("Tarefas:")
                for i, tarefa in enumerate(self.tarefas, 1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(f"Erro ao listar tarefas: {e}")

    def remover_tarefa(self, indice):
        try:
            if not self.tarefas:
                raise ValueError("Nenhuma tarefa encontrada.")
            elif 1 <= indice <= len(self.tarefas):
                removed_task = self.tarefas.pop(indice - 1)
                print(f"Tarefa '{removed_task}' removida com sucesso.")
            else:
                raise IndexError("Índice inválido para remover tarefa.")
        except Exception as e:
            print(f"Erro ao remover tarefa: {e}")

    def sair(self):
        try:
            print("Saindo do programa...")
            exit()
        except Exception as e:
            print(f"Erro ao sair: {e}")


if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nMenu:")
        print("1. Adicionar Tarefa")
        print("2. Listar Tarefas")
        print("3. Remover Tarefa")
        print("4. Sair")

        choice = input("Digite a opção desejada: ")

        if choice == "1":
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif choice == "2":
            tarefa1.listar_tarefas()
        elif choice == "3":
            indice = int(input("Digite o índice da tarefa a ser removida: "))
            tarefa1.remover_tarefa(indice)
        elif choice == "4":
            tarefa1.sair()
        else:
            print("Opção inválida. Tente novamente.")