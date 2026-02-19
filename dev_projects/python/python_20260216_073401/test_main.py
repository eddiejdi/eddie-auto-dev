import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        assert "Fazer compras" in tarefa1.tarefas, "Tarefa não adicionada corretamente"

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.listar_tarefas()
        assert "Fazer compras" in tarefa1.tarefas, "Tarefas não listadas corretamente"

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.remover_tarefa(1)
        assert "Fazer compras" not in tarefa1.tarefas, "Tarefa não removida corretamente"

    def test_sair(self):
        tarefa1 = Tarefa1()
        with pytest.raises(SystemExit) as exc_info:
            tarefa1.sair()
        assert exc_info.value.code == 0, "Programa não saiu corretamente"