import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert "Tarefa 1" in tarefa1.listar_tarefas()

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        assert ["Tarefa 1", "Tarefa 2"] == tarefa1.listar_tarefas()

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        tarefa1.remover_tarefa(0)
        assert "Tarefa 2" in tarefa1.listar_tarefas()

    def test_remover_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)

    def test_remover_tarefa_indice_excedente(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(2)