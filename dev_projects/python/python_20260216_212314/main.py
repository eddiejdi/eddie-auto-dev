class Tarefa1:
    def __init__(self):
        self.items = []

    def add_item(self, item):
        if not isinstance(item, str):
            raise ValueError("Item deve ser uma string")
        self.items.append(item)

    def remove_item(self, index):
        if index < 0 or index >= len(self.items):
            raise IndexError("Índice inválido")
        del self.items[index]

    def list_items(self):
        return self.items

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.add_item("Tarefa 1")
    tarefa1.add_item("Tarefa 2")
    print(tarefa1.list_items())  # Output: ['Tarefa 1', 'Tarefa 2']
    tarefa1.remove_item(0)
    print(tarefa1.list_items())  # Output: ['Tarefa 2']