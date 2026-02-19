import random

class Tarefa1:
    def __init__(self):
        self.items = [f"Item {i}" for i in range(10)]
        self.selected_items = []

    def selecionar_item(self):
        if not self.items:
            raise ValueError("Não há itens para selecionar")
        
        item = random.choice(self.items)
        self.items.remove(item)
        self.selected_items.append(item)
        return item

    def listar_selecionados(self):
        return self.selected_items

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    
    try:
        print("Selecione um item:")
        selected_item = tarefa1.selecionar_item()
        print(f"Item selecionado: {selected_item}")
        
        print("\nLista de itens selecionados:")
        for item in tarefa1.listar_selecionados():
            print(item)
    except ValueError as e:
        print(e)