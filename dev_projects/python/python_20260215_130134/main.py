class Tarefa1:
    def __init__(self):
        self.items = []

    def adicionar_item(self, item):
        try:
            self.items.append(item)
            print(f"Item '{item}' adicionado com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar item: {e}")

    def listar_itens(self):
        try:
            if not self.items:
                print("Nenhum item encontrado.")
            else:
                for i, item in enumerate(self.items, start=1):
                    print(f"{i}. {item}")
        except Exception as e:
            print(f"Erro ao listar itens: {e}")

    def remover_item(self, index):
        try:
            if 0 < index <= len(self.items):
                removed_item = self.items.pop(index - 1)
                print(f"Item '{removed_item}' removido com sucesso.")
            else:
                print("Índice inválido. O item não foi removido.")
        except Exception as e:
            print(f"Erro ao remover item: {e}")

    def buscar_item(self, item):
        try:
            if item in self.items:
                print(f"Item '{item}' encontrado.")
            else:
                print("Item não encontrado.")
        except Exception as e:
            print(f"Erro ao buscar item: {e}")


if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nTarefas 1")
        print("1. Adicionar Item")
        print("2. Listar Itens")
        print("3. Remover Item")
        print("4. Buscar Item")
        print("5. Sair")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            item = input("Digite o nome do item: ")
            tarefa1.adicionar_item(item)
        elif opcao == "2":
            tarefa1.listar_itens()
        elif opcao == "3":
            index = int(input("Digite o índice do item a remover: "))
            tarefa1.remover_item(index)
        elif opcao == "4":
            item = input("Digite o nome do item a buscar: ")
            tarefa1.buscar_item(item)
        elif opcao == "5":
            print("Saindo...")
            break
        else:
            print("Opção inválida. Tente novamente.")