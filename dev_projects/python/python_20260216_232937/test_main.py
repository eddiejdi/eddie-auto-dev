import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        assert "Fazer compras" in tarefa1.tarefas

    def test_adicionar_tarefa_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa(123)

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Estudar Python")
        assert "Fazer compras" in tarefa1.listar_tarefas() and "Estudar Python" in tarefa1.listar_tarefas()

    def test_listar_tarefas_vazia(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_tarefas() == []

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.remover_tarefa("Estudar Python")
        assert "Estudar Python" not in tarefa1.listar_tarefas()

    def test_remover_tarefa_inexistente(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa("Estudar Python")

    def test_remove_tarefa_vazia(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.remove_tarefa("Fazer compras")