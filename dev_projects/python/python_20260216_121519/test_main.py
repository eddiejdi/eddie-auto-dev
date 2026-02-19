import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("tarefa1")
        assert len(tarefa1.tarefas) == 1
        assert tarefa1.tarefas[0] == "tarefa1"

    def test_adicionar_tarefa_invalida(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa(123)

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("tarefa1")
        assert tarefa1.listar_tarefas() == "tarefa1\n"

    def test_listar_tarefas_vazia(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_tarefas() == ""

    def test_remover_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(0)

    def test_remover_tarefa_positivo(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("tarefa1")
        tarefa1.adicionar_tarefa("tarefa2")
        assert len(tarefa1.tarefas) == 2
        tarefa1.remover_tarefa(1)
        assert len(tarefa1.tarefas) == 1
        assert tarefa1.tarefas[0] == "tarefa1"

    def test_remover_tarefa_negativo(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)

    def test_remover_tarefa_zero(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(0)