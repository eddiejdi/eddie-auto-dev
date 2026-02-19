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
            if self.tarefas:
                print("Tarefas:")
                for i, tarefa in enumerate(self.tarefas, 1):
                    print(f"{i}. {tarefa}")
            else:
                print("Nenhuma tarefa adicionada.")
        except Exception as e:
            print(f"Erro ao listar tarefas: {e}")

    def remover_tarefa(self, posicao):
        try:
            if 1 <= posicao <= len(self.tarefas):
                removed_task = self.tarefas.pop(posicao - 1)
                print(f"Tarefa '{removed_task}' removida com sucesso.")
            else:
                raise ValueError("Posição inválida para remover tarefa.")
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
        
        opcao = input("Digite a opção desejada: ")
        
        if opcao == "1":
            tarefa = input("Digite a tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao == "2":
            tarefa1.listar_tarefas()
        elif opcao == "3":
            posicao = int(input("Digite a posição da tarefa a remover (1-based): "))
            tarefa1.remover_tarefa(posicao)
        elif opcao == "4":
            print("Saindo do programa.")
            break
        else:
            print("Opção inválida. Tente novamente.")