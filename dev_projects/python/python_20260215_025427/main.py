import random

class Tarefa1:
    def __init__(self):
        self.items = []

    def adicionar_item(self, item):
        if not isinstance(item, str):
            raise ValueError("Item deve ser uma string")
        self.items.append(item)

    def remover_item(self, index):
        if index < 0 or index >= len(self.items):
            raise IndexError("Índice inválido")
        del self.items[index]

    def listar_itens(self):
        return self.items

    def embaralhar_itens(self):
        random.shuffle(self.items)

    @classmethod
    def main(cls):
        tarefa = Tarefa1()
        while True:
            print("\nMenu:")
            print("1. Adicionar item")
            print("2. Remover item")
            print("3. Listar itens")
            print("4. Embaralhar itens")
            print("5. Sair")

            choice = input("Escolha uma opção: ")

            if choice == "1":
                item = input("Digite o item a adicionar: ")
                tarefa.adicionar_item(item)
            elif choice == "2":
                index = int(input("Digite o índice do item a remover: "))
                tarefa.remover_item(index)
            elif choice == "3":
                print("Itens na lista:")
                for i, item in enumerate(tarefa.listar_itens()):
                    print(f"{i+1}. {item}")
            elif choice == "4":
                tarefa.embaralhar_itens()
                print("Lista embaralhada:")
                for i, item in enumerate(tarefa.listar_itens()):
                    print(f"{i+1}. {item}")
            elif choice == "5":
                print("Saindo...")
                break
            else:
                print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    Tarefa1.main()