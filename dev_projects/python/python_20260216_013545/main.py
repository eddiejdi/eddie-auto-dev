class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def add_tarefa(self, tarefa):
        try:
            if not isinstance(tarefa, str):
                raise ValueError("Tarefa deve ser uma string")
            self.tarefas.append(tarefa)
            print(f"Tarefa '{tarefa}' adicionada com sucesso.")
        except ValueError as e:
            print(e)

    def listar_tarefas(self):
        try:
            if not self.tarefas:
                print("Nenhuma tarefa encontrada.")
            else:
                print("Tarefas:")
                for i, tarefa in enumerate(self.tarefas, 1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(e)

    def remover_tarefa(self, indice):
        try:
            if not isinstance(indice, int) or indice < 1 or indice > len(self.tarefas):
                raise ValueError("Índice inválido.")
            removed_task = self.tarefas.pop(indice - 1)
            print(f"Tarefa '{removed_task}' removida com sucesso.")
        except ValueError as e:
            print(e)

    def sair(self):
        try:
            print("Saindo do programa...")
            exit()
        except Exception as e:
            print(e)

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
            tarefa1.add_tarefa(input("Digite a tarefa: "))
        elif choice == "2":
            tarefa1.listar_tarefas()
        elif choice == "3":
            indice = int(input("Digite o índice da tarefa a remover: "))
            tarefa1.remover_tarefa(indice)
        elif choice == "4":
            tarefa1.sair()
        else:
            print("Opção inválida. Tente novamente.")