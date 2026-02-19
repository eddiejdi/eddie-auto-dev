class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if not isinstance(tarefa, str):
                raise ValueError("Tarefa deve ser uma string")
            self.tarefas.append(tarefa)
            print(f"Tarefa '{tarefa}' adicionada com sucesso.")
        except ValueError as e:
            print(e)

    def listar_tarefas(self):
        try:
            if len(self.tarefas) == 0:
                print("Nenhuma tarefa encontrada.")
            else:
                print("Tarefas:")
                for i, tarefa in enumerate(self.tarefas, start=1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(e)

    def remover_tarefa(self, index):
        try:
            if not isinstance(index, int) or index < 1 or index > len(self.tarefas):
                raise IndexError("Índice inválido.")
            removed_task = self.tarefas.pop(index - 1)
            print(f"Tarefa '{removed_task}' removida com sucesso.")
        except IndexError as e:
            print(e)

    def buscar_tarefa(self, tarefa):
        try:
            if not isinstance(tarefa, str):
                raise ValueError("Tarefa deve ser uma string")
            for i, t in enumerate(self.tarefas, start=1):
                if t == tarefa:
                    print(f"Tarefa '{tarefa}' encontrada na posição {i}.")
                    return
            print(f"Tarefa '{tarefa}' não encontrada.")
        except ValueError as e:
            print(e)

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    while True:
        print("\nMenu:")
        print("1. Adicionar Tarefa")
        print("2. Listar Tarefas")
        print("3. Remover Tarefa")
        print("4. Buscar Tarefa")
        print("5. Sair")

        choice = input("Escolha uma opção: ")

        if choice == "1":
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif choice == "2":
            tarefa1.listar_tarefas()
        elif choice == "3":
            index = int(input("Digite o índice da tarefa a remover: "))
            tarefa1.remover_tarefa(index)
        elif choice == "4":
            tarefa = input("Digite a tarefa a buscar: ")
            tarefa1.buscar_tarefa(tarefa)
        elif choice == "5":
            print("Saindo do programa.")
            break
        else:
            print("Opção inválida. Tente novamente.")