import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert len(tarefa1.tarefas) == 1, "Tarefa não adicionada corretamente"

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        tarefa1.listar_tarefas()
        assert "1. Tarefa 1" in tarefa1.tarefas, "Lista de tarefas incorreta"
        assert "2. Tarefa 2" in tarefa1.tarefas, "Lista de tarefas incorreta"

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.remover_tarefa(0)
        assert len(tarefa1.tarefas) == 0, "Tarefa não removida corretamente"

    def test_remover_indice_invalido(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(2)