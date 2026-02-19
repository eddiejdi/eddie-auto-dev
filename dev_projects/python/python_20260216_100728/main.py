class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        if not self.tarefas:
            return "Nenhuma tarefa cadastrada."
        return "\n".join([f"{i+1}. {tarefa}" for i, tarefa in enumerate(self.tarefas)])

    def remover_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
            return "Tarefa removida com sucesso."
        else:
            return "Índice inválido."

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
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao == "2":
            print(tarefa1.listar_tarefas())
        elif opcao == "3":
            indice = int(input("Digite o índice da tarefa a ser removida: "))
            print(tarefa1.remover_tarefa(indice))
        elif opcao == "4":
            break
        else:
            print("Opção inválida. Tente novamente.")