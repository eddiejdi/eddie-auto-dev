import random

class Tarefa1:
    def __init__(self):
        self.items = []
        self.random_items = []

    def add_item(self, item):
        if not isinstance(item, str):
            raise ValueError("Item deve ser uma string")
        self.items.append(item)

    def remove_item(self, index):
        if index < 0 or index >= len(self.items):
            raise IndexError("Índice inválido")
        del self.items[index]

    def get_random_items(self, count):
        if not isinstance(count, int) or count <= 0:
            raise ValueError("Quantidade deve ser um número positivo")
        if count > len(self.items):
            count = len(self.items)
        self.random_items.extend(random.sample(self.items, count))

    def print_items(self):
        for item in self.items:
            print(item)

    def print_random_items(self):
        for item in self.random_items:
            print(item)

# Exemplo de uso
if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.add_item("Item 1")
    tarefa1.add_item("Item 2")
    tarefa1.add_item("Item 3")

    try:
        tarefa1.remove_item(0)
        tarefa1.get_random_items(2)
        tarefa1.print_items()
        tarefa1.print_random_items()
    except ValueError as e:
        print(f"Erro: {e}")
    except IndexError as e:
        print(f"Erro: {e}")