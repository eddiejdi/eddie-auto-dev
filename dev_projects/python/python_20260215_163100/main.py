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
                raise ValueError("Índice inválido")
            removed_task = self.tarefas.pop(indice - 1)
            print(f"Tarefa '{removed_task}' removida com sucesso.")
        except ValueError as e:
            print(e)

    def buscar_tarefa(self, palavra_chave):
        try:
            if not isinstance(palavra_chave, str):
                raise ValueError("Palavra-chave deve ser uma string")
            found_tasks = [tarefa for tarefa in self.tarefas if palavra_chave.lower() in tarefa.lower()]
            if found_tasks:
                print("Tarefas encontradas:")
                for i, tarefa in enumerate(found_tasks, 1):
                    print(f"{i}. {tarefa}")
            else:
                print("Nenhuma tarefa encontrada.")
        except Exception as e:
            print(e)

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nTarefas 1")
        print("1. Adicionar tarefa")
        print("2. Listar tarefas")
        print("3. Remover tarefa")
        print("4. Buscar tarefa")
        print("5. Sair")

        choice = input("Escolha uma opção: ")

        if choice == "1":
            tarefa1.adicionar_tarefa(input("Digite a tarefa: "))
        elif choice == "2":
            tarefa1.listar_tarefas()
        elif choice == "3":
            indice = int(input("Digite o índice da tarefa a remover: "))
            tarefa1.remover_tarefa(indice)
        elif choice == "4":
            palavra_chave = input("Digite a palavra-chave para buscar: ")
            tarefa1.buscar_tarefa(palavra_chave)
        elif choice == "5":
            print("Saindo...")
            break
        else:
            print("Opção inválida. Tente novamente.")