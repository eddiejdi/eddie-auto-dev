import random

class Tarefa1:
    def __init__(self):
        self.items = []
        self.max_items = 5

    def add_item(self, item):
        if len(self.items) < self.max_items:
            self.items.append(item)
        else:
            raise ValueError("Tarefa cheia")

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
        else:
            raise IndexError("Índice inválido")

    def list_items(self):
        return self.items

def main():
    tarefa1 = Tarefa1()
    
    while True:
        print("\nTarefas:")
        for i, item in enumerate(tarefa1.list_items()):
            print(f"{i+1}. {item}")
        
        print("\nOpções:")
        print("1. Adicionar item")
        print("2. Remover item")
        print("3. Listar itens")
        print("4. Sair")
        
        choice = input("Escolha uma opção: ")
        
        if choice == "1":
            item = input("Digite o item a adicionar: ")
            tarefa1.add_item(item)
        elif choice == "2":
            index = int(input("Digite o índice do item a remover: "))
            tarefa1.remove_item(index)
        elif choice == "3":
            print("\nItens:")
            for i, item in enumerate(tarefa1.list_items()):
                print(f"{i+1}. {item}")
        elif choice == "4":
            break
        else:
            print("Opção inválida")

if __name__ == "__main__":
    main()