import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

class TestTarefa1:
    @pytest.mark.parametrize("tarefa", ["Tarefa 1", "Tarefa 2"])
    def test_adicionar_tarefa(self, tarefa):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(tarefa)
        assert tarefa in tarefa1.tarefas

    @pytest.mark.parametrize("tarefa", ["Tarefa 1", "Tarefa 2"])
    def test_listar_tarefas(self, tarefa):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(tarefa)
        assert tarefa in tarefa1.listar_tarefas()

    @pytest.mark.parametrize("index", [0, 1])
    def test_remover_tarefa(self, index):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        tarefa1.remover_tarefa(index)
        assert len(tarefa1.tarefas) == 1

    @pytest.mark.parametrize("index", [-1, 2])
    def test_remover_tarefa_invalido(self, index):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(index)

    @pytest.mark.parametrize("tarefa", ["Tarefa 1", "Tarefa 2"])
    def test_adicionar_tarefa_string_vazia(self, tarefa):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("")
        assert not tarefa1.tarefas

    @pytest.mark.parametrize("tarefa", ["Tarefa 1", "Tarefa 2"])
    def test_adicionar_tarefa_none(self, tarefa):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(None)
        assert not tarefa1.tarefas