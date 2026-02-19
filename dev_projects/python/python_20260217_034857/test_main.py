import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        assert "Fazer compras" in tarefa1.listar_tarefas()

    def test_adicionar_tarefa_invalido(self):
        with pytest.raises(ValueError):
            tarefa1 = Tarefa1()
            tarefa1.adicionar_tarefa(123)

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Ler livro")
        assert ["Fazer compras", "Ler livro"] == tarefa1.listar_tarefas()

    def test_listar_tarefas_vazia(self):
        tarefa1 = Tarefa1()
        assert [] == tarefa1.listar_tarefas()

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Ler livro")
        tarefa1.remover_tarefa(0)
        assert ["Ler livro"] == tarefa1.listar_tarefas()

    def test_remover_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)

    def test_remover_tarefa_indice_excedente(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(2)