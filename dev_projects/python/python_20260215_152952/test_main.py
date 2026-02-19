import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Estudar Python")
        assert "Estudar Python" in tarefa1.tarefas

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.adicionar_tarefa("Lavar o carro")
        assert tarefa1.listar_tarefas() == ["Estudar Python", "Lavar o carro"]

    def test_concluir_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.concluir_tarefa(0)
        assert len(tarefa1.tarefas) == 1
        assert "Estudar Python" not in tarefa1.listar_tarefas()

    def test_listar_concluidas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.concluir_tarefa(0)
        assert len(tarefa1.concluidas) == 1
        assert "Estudar Python" in tarefa1.listar_concluidas()

    def test_adicionar_tarefa_invalida(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa(123)

    def test_listar_tarefas_vazia(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_tarefas() == []

    def test_concluir_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.concluir_tarefa(2)

    def test_listar_concluidas_vazia(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_concluidas() == []

    def test_adicionar_tarefa_string_vazia(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa("")

    def test_listar_tarefas_string_vazia(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_tarefas() == []

    def test_concluir_tarefa_string_vazia(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.concluir_tarefa(0)

    def test_listar_concluidas_string_vazia(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_concluidas() == []