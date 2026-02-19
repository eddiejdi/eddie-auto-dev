class Tarefa1:
    def __init__(self):
        self.items = []

    def adicionar_item(self, item):
        try:
            self.items.append(item)
            print(f"Item '{item}' adicionado com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar item: {e}")

    def remover_item(self, item):
        try:
            if item in self.items:
                self.items.remove(item)
                print(f"Item '{item}' removido com sucesso.")
            else:
                print(f"Item '{item}' não encontrado.")
        except Exception as e:
            print(f"Erro ao remover item: {e}")

    def listar_itens(self):
        try:
            if not self.items:
                print("Nenhum item disponível.")
            else:
                print("Itens disponíveis:")
                for i, item in enumerate(self.items, start=1):
                    print(f"{i}. {item}")
        except Exception as e:
            print(f"Erro ao listar itens: {e}")

    def buscar_item(self, item):
        try:
            if item in self.items:
                print(f"Item '{item}' encontrado.")
            else:
                print(f"Item '{item}' não encontrado.")
        except Exception as e:
            print(f"Erro ao buscar item: {e}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    while True:
        print("\nMenu:")
        print("1. Adicionar Item")
        print("2. Remover Item")
        print("3. Listar Itens")
        print("4. Buscar Item")
        print("5. Sair")

        choice = input("Escolha uma opção: ")

        if choice == "1":
            item = input("Digite o item a adicionar: ")
            tarefa1.adicionar_item(item)
        elif choice == "2":
            item = input("Digite o item a remover: ")
            tarefa1.remover_item(item)
        elif choice == "3":
            tarefa1.listar_itens()
        elif choice == "4":
            item = input("Digite o item a buscar: ")
            tarefa1.buscar_item(item)
        elif choice == "5":
            print("Saindo do programa.")
            break
        else:
            print("Opção inválida. Tente novamente.")