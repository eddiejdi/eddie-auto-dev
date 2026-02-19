import pytest
from typing import *
from collections import *

class Tarefa1:
    def __init__(self):
        self.items = []

    def adicionar_item(self, item: str) -> None:
        self.items.append(item)
        print(f"Item '{item}' adicionado com sucesso.")

    def remover_item(self, item: str) -> None:
        if item in self.items:
            self.items.remove(item)
            print(f"Item '{item}' removido com sucesso.")
        else:
            print(f"Item '{item}' não encontrado.")

    def listar_itens(self) -> List[str]:
        return self.items

    def buscar_item(self, item: str) -> Optional[str]:
        if item in self.items:
            return item
        else:
            return None

# Exemplo de uso
if __name__ == "__main__":
    tarefa1 = Tarefa1()

    # Casos de sucesso com valores válidos
    assert tarefa1.adicionar_item("Item 1") is None
    assert tarefa1.listar_itens() == ["Item 1"]
    assert tarefa1.buscar_item("Item 1") == "Item 1"

    # Casos de erro (divisão por zero, valores inválidos, etc)
    with pytest.raises(ValueError):
        tarefa1.adicionar_item(0)

    # Edge cases (valores limite, strings vazias, None, etc)
    assert tarefa1.listar_itens() == []
    assert tarefa1.buscar_item("") is None
    assert tarefa1.buscar_item(None) is None