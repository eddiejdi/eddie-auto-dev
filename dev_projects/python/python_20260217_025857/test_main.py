import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert "Tarefa 1" in tarefa1.tarefas, "Tarefa não adicionada corretamente"

    def test_adicionar_tarefa_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa(123)

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert "Tarefa 1" in tarefa1.listar_tarefas(), "Lista de tarefas não retornada corretamente"

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        assert len(tarefa1.listar_tarefas()) == 2, "Lista de tarefas não atualizada corretamente"
        tarefa1.remover_tarefa(0)
        assert len(tarefa1.listar_tarefas()) == 1, "Lista de tarefas não atualizada corretamente"

    def test_remover_tarefa_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(2)