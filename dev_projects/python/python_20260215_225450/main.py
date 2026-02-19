class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            self.tarefas.append(tarefa)
            print(f"Tarefa '{tarefa}' adicionada com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar tarefa: {e}")

    def listar_tarefas(self):
        try:
            if not self.tarefas:
                print("Nenhuma tarefa encontrada.")
            else:
                print("Tarefas:")
                for i, tarefa in enumerate(self.tarefas, start=1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(f"Erro ao listar tarefas: {e}")

    def remover_tarefa(self, indice):
        try:
            if 0 < indice <= len(self.tarefas):
                removed_task = self.tarefas.pop(indice - 1)
                print(f"Tarefa '{removed_task}' removida com sucesso.")
            else:
                print("Índice de tarefa inválido.")
        except Exception as e:
            print(f"Erro ao remover tarefa: {e}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nMenu:")
        print("1. Adicionar Tarefa")
        print("2. Listar Tarefas")
        print("3. Remover Tarefa")
        print("4. Sair")

        escolha = input("Escolha uma opção: ")

        if escolha == "1":
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif escolha == "2":
            tarefa1.listar_tarefas()
        elif escolha == "3":
            indice = int(input("Digite o índice da tarefa a remover: "))
            tarefa1.remover_tarefa(indice)
        elif escolha == "4":
            print("Saindo do programa.")
            break
        else:
            print("Opção inválida. Tente novamente.")