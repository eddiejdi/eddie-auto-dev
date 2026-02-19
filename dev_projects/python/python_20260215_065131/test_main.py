import pytest

class TestTarefa1:
    def setup_method(self):
        self.tarefa1 = Tarefa1()

    def test_adicionar_item_sucesso(self):
        item = "Item 1"
        self.tarefa1.adicionar_item(item)
        assert item in self.tarefa1.items, f"Item '{item}' não encontrado."

    def test_adicionar_item_erro(self):
        with pytest.raises(Exception) as e:
            self.tarefa1.adicionar_item(0)
        assert str(e.value).startswith("Erro ao adicionar item"), "Erro incorreto"

    def test_remover_item_sucesso(self):
        item = "Item 1"
        self.tarefa1.adicionar_item(item)
        self.tarefa1.remover_item(item)
        assert item not in self.tarefa1.items, f"Item '{item}' não removido."

    def test_remover_item_erro(self):
        with pytest.raises(Exception) as e:
            self.tarefa1.remover_item("Item 2")
        assert str(e.value).startswith("Erro ao remover item"), "Erro incorreto"

    def test_listar_itens_sucesso(self):
        itens = ["Item 1", "Item 2"]
        for item in itens:
            self.tarefa1.adicionar_item(item)
        tarefa1.listar_itens()
        assert len(tarefa1.items) == len(itens), f"Lista de itens incorreta"

    def test_listar_itens_erro(self):
        with pytest.raises(Exception) as e:
            tarefa1.listar_itens()
        assert str(e.value).startswith("Erro ao listar itens"), "Erro incorreto"

    def test_buscar_item_sucesso(self):
        item = "Item 1"
        self.tarefa1.adicionar_item(item)
        resultado = self.tarefa1.buscar_item(item)
        assert resultado == f"Item '{item}' encontrado.", f"Resultado incorreto"

    def test_buscar_item_erro(self):
        with pytest.raises(Exception) as e:
            self.tarefa1.buscar_item("Item 3")
        assert str(e.value).startswith("Erro ao buscar item"), "Erro incorreto"