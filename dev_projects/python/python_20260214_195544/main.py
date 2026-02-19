import argparse

class Tarefa1:
    def __init__(self):
        self.items = []

    def adicionar_item(self, item):
        self.items.append(item)

    def remover_item(self, item):
        if item in self.items:
            self.items.remove(item)
        else:
            print(f"Item '{item}' não encontrado.")

    def listar_itens(self):
        return self.items

def main():
    parser = argparse.ArgumentParser(description="Tarefa 1")
    parser.add_argument("opcao", choices=["adicionar", "remover", "listar"], help="Opção a ser executada")
    parser.add_argument("item", nargs="?", help="Item a ser adicionado ou removido")

    args = parser.parse_args()

    tarefa1 = Tarefa1()

    if args.opcao == "adicionar":
        tarefa1.adicionar_item(args.item)
    elif args.opcao == "remover":
        tarefa1.remover_item(args.item)
    elif args.opcao == "listar":
        print("Itens:")
        for item in tarefa1.listar_itens():
            print(item)

if __name__ == "__main__":
    main()