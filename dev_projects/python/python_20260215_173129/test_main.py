import pytest

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
                print("Nenhum item na lista.")
            else:
                print("Itens na lista:")
                for item in self.items:
                    print(item)
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

def test_adicionar_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    assert "Item 1" in tarefa1.items

def test_remover_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.remover_item("Item 1")
    assert len(tarefa1.items) == 0

def test_listar_itens():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.adicionar_item("Item 2")
    tarefa1.listar_itens()
    assert "Item 1" in tarefa1.items
    assert "Item 2" in tarefa1.items

def test_buscar_item():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_item("Item 1")
    tarefa1.buscar_item("Item 1")
    assert "Item 1" in tarefa1.items