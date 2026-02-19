import pytest
from tarefa1 import Tarefa1

class TestTarefa1:
    def test_adicionar_item(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_item("Item 1")
        assert "Item 1" in tarefa1.listar_itens()

    def test_remover_item(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_item("Item 1")
        tarefa1.remover_item("Item 1")
        with pytest.raises(ValueError):
            tarefa1.remover_item("Item 2")

    def test_listar_itens(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_item("Item 1")
        tarefa1.adicionar_item("Item 2")
        assert "Item 1" in tarefa1.listar_itens() and "Item 2" in tarefa1.listar_itens()

    def test_adicionar_item_invalido(self):
        with pytest.raises(ValueError):
            Tarefa1().adicionar_item(123)

    def test_remover_item_invalido(self):
        with pytest.raises(ValueError):
            Tarefa1().remover_item("Item 1")

    def test_listar_itens_vazio(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_itens() == []