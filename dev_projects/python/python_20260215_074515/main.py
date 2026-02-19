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
        except ValueError as e:
            print(e)

    def listar_tarefas(self):
        try:
            if len(self.tarefas) == 0:
                print("Não há tarefas para listar.")
            else:
                for i, tarefa in enumerate(self.tarefas, start=1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(e)

    def remover_tarefa(self, indice):
        try:
            if isinstance(indice, int) and 0 <= indice < len(self.tarefas):
                removed_task = self.tarefas.pop(indice)
                print(f"Tarefa '{removed_task}' removida com sucesso.")
            else:
                raise ValueError("Índice inválido ou tarefa não encontrada.")
        except ValueError as e:
            print(e)

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    while True:
        print("\nTarefas disponíveis:")
        for i, tarefa in enumerate(tarefa1.tarefas, start=1):
            print(f"{i}. {tarefa}")
        
        print("\nOpções:")
        print("1. Adicionar tarefa")
        print("2. Listar tarefas")
        print("3. Remover tarefa")
        print("4. Sair")
        
        opcao = input("Escolha uma opção: ")
        
        if opcao == "1":
            tarefa = input("Digite a nova tarefa: ")
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