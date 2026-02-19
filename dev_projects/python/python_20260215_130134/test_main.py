import pytest

class TestTarefa1:
    def setup_method(self):
        self.tarefa1 = Tarefa1()

    def test_adicionar_item_sucesso(self):
        # Caso de sucesso com valor válido
        item = "Item 1"
        self.tarefa1.adicionar_item(item)
        assert item in self.tarefa1.items

    def test_adicionar_item_erro_divisao_zero(self):
        # Caso de erro (divisão por zero)
        with pytest.raises(ZeroDivisionError):
            self.tarefa1.adicionar_item("0")

    def test_listar_itens_sucesso(self):
        # Caso de sucesso com valores válidos
        item1 = "Item 1"
        item2 = "Item 2"
        self.tarefa1.adicionar_item(item1)
        self.tarefa1.adicionar_item(item2)
        self.tarefa1.listar_itens()
        assert item1 in self.tarefa1.items and item2 in self.tarefa1.items

    def test_listar_itens_erro_lista_vazia(self):
        # Caso de erro (lista vazia)
        with pytest.raises(IndexError):
            self.tarefa1.listar_itens()

    def test_remover_item_sucesso(self):
        # Caso de sucesso com valor válido
        item = "Item 1"
        self.tarefa1.adicionar_item(item)
        index = self.tarefa1.items.index(item) + 1
        self.tarefa1.remover_item(index)
        assert item not in self.tarefa1.items

    def test_remover_item_erro_indice_invalido(self):
        # Caso de erro (índice inválido)
        with pytest.raises(IndexError):
            self.tarefa1.remover_item(0)

    def test_buscar_item_sucesso(self):
        # Caso de sucesso com valor válido
        item = "Item 1"
        self.tarefa1.adicionar_item(item)
        self.tarefa1.buscar_item(item)
        assert item in self.tarefa1.items

    def test_buscar_item_erro_item_nao_encontrado(self):
        # Caso de erro (item não encontrado)
        with pytest.raises(ValueError):
            self.tarefa1.buscar_item("Item Não Encontrado")