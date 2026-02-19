import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        if not self.tarefas:
            return "Nenhuma tarefa cadastrada."
        return "\n".join([f"{i+1}. {tarefa}" for i, tarefa in enumerate(self.tarefas)])

    def remover_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
            return "Tarefa removida com sucesso."
        else:
            return "Índice inválido."

class TestTarefa1:
    @pytest.fixture
    def tarefa1(self):
        return Tarefa1()

    def test_adicionar_tarefa(self, tarefa1):
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert len(tarefa1.tarefas) == 1

    def test_listar_tarefas(self, tarefa1):
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        assert tarefa1.listar_tarefas() == "1. Tarefa 1\n2. Tarefa 2"

    def test_remover_tarefa(self, tarefa1):
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.remover_tarefa(0)
        assert len(tarefa1.tarefas) == 0

    def test_adicionar_tarefa_vazia(self, tarefa1):
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa("")

    def test_listar_tarefas_vazia(self, tarefa1):
        assert tarefa1.listar_tarefas() == "Nenhuma tarefa cadastrada."

    def test_remover_tarefa_indice_invalido(self, tarefa1):
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)

    def test_adicionar_tarefa_none(self, tarefa1):
        with pytest.raises(ValueError):
            tarefa1.adicionar_tarefa(None)