import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if isinstance(tarefa, str):
                self.tarefas.append(tarefa)
                return f"Tarefa '{tarefa}' adicionada com sucesso."
            else:
                raise ValueError("A tarefa deve ser uma string.")
        except Exception as e:
            return f"Erro: {str(e)}"

    def listar_tarefas(self):
        try:
            if self.tarefas:
                return "\n".join(self.tarefas)
            else:
                return "Nenhuma tarefa adicionada."
        except Exception as e:
            return f"Erro: {str(e)}"

    def remover_tarefa(self, index):
        try:
            if 0 <= index < len(self.tarefas):
                removed_task = self.tarefas.pop(index)
                return f"Tarefa '{removed_task}' removida com sucesso."
            else:
                raise IndexError("Índice inválido.")
        except Exception as e:
            return f"Erro: {str(e)}"

    def __repr__(self):
        return f"Tarefa1({self.tarefas})"


class TestTarefa1:
    def test_adicionar_tarefa(self, tarefa1):
        assert tarefa1.adicionar_tarefa("Entregar projeto") == "Tarefa 'Entregar projeto' adicionada com sucesso."
        assert tarefa1.adicionar_tarefa(42) == "Erro: A tarefa deve ser uma string."

    def test_listar_tarefas(self, tarefa1):
        assert tarefa1.listar_tarefas() == "Nenhuma tarefa adicionada."
        tarefa1.adicionar_tarefa("Entregar projeto")
        assert tarefa1.listar_tarefas() == "Entregar projeto"

    def test_remover_tarefa(self, tarefa1):
        assert tarefa1.remover_tarefa(0) == "Tarefa 'Entregar projeto' removida com sucesso."
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(-1)
        with pytest.raises(IndexError):
            tarefa1.remover_tarefa(len(tarefa1.tarefas))

    def test_repr(self, tarefa1):
        assert str(tarefa1) == "Tarefa1([])"