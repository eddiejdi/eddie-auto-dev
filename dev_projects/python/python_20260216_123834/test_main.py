import pytest
from unittest.mock import patch

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

def test_selecionar_item():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso com valores válidos
    assert tarefa1.selecionar_item() in tarefa1.items, "Item selecionado não está na lista"
    
    # Caso de erro (divisão por zero)
    with pytest.raises(ValueError):
        tarefa1.selecionar_item()

def test_listar_selecionados():
    tarefa1 = Tarefa1()
    
    # Caso de sucesso com valores válidos
    assert len(tarefa1.listar_selecionados()) == 0, "Lista de itens selecionados não está vazia"