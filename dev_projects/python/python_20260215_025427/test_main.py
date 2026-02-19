import pytest
from tarefa1 import Tarefa1

class TestTarefa1:
    def test_adicionar_item(self):
        tarefa = Tarefa1()
        tarefa.adicionar_item("Item 1")
        assert "Item 1" in tarefa.listar_itens()

    def test_remover_item(self):
        tarefa = Tarefa1()
        tarefa.adicionar_item("Item 1")
        tarefa.remover_item(0)
        assert len(tarefa.listar_itens()) == 0

    def test_listar_itens(self):
        tarefa = Tarefa1()
        tarefa.adicionar_item("Item 1")
        tarefa.adicionar_item("Item 2")
        assert tarefa.listar_itens() == ["Item 1", "Item 2"]

    def test_embaralhar_itens(self):
        tarefa = Tarefa1()
        tarefa.adicionar_item("Item 1")
        tarefa.adicionar_item("Item 2")
        tarefa.embaralhar_itens()
        assert len(tarefa.listar_itens()) == 2

    def test_main(self):
        with pytest.raises(SystemExit) as exc_info:
            Tarefa1.main()
        assert "Saindo..." in str(exc_info.value)