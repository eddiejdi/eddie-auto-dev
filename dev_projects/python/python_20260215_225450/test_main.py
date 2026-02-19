import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            self.tarefas.append(tarefa)
            print(f"Tarefa '{tarefa}' adicionada com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar tarefa: {e}")

    def listar_tarefas(self):
        try:
            if not self.tarefas:
                print("Nenhuma tarefa encontrada.")
            else:
                print("Tarefas:")
                for i, tarefa in enumerate(self.tarefas, start=1):
                    print(f"{i}. {tarefa}")
        except Exception as e:
            print(f"Erro ao listar tarefas: {e}")

    def remover_tarefa(self, indice):
        try:
            if 0 < indice <= len(self.tarefas):
                removed_task = self.tarefas.pop(indice - 1)
                print(f"Tarefa '{removed_task}' removida com sucesso.")
            else:
                print("Índice de tarefa inválido.")
        except Exception as e:
            print(f"Erro ao remover tarefa: {e}")

class TestTarefa1:
    def test_adicionar_tarefa(self, tarefa1):
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert len(tarefa1.tarefas) == 1
        assert tarefa1.tarefas[0] == "Tarefa 1"

    def test_listar_tarefas(self, tarefa1):
        tarefa1.listar_tarefas()
        assert "Tarefas:" in tarefa1.output

    def test_remover_tarefa(self, tarefa1):
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.remover_tarefa(1)
        assert len(tarefa1.tarefas) == 0

    def test_adicionar_tarefa_invalida(self, tarefa1):
        with pytest.raises(Exception):
            tarefa1.adicionar_tarefa(None)

    def test_listar_tarefas_vazia(self, tarefa1):
        tarefa1.listar_tarefas()
        assert "Nenhuma tarefa encontrada." in tarefa1.output

    def test_remover_tarefa_invalida(self, tarefa1):
        with pytest.raises(Exception):
            tarefa1.remover_tarefa(0)

    def test_adicionar_tarefa_divisao_zero(self, tarefa1):
        with pytest.raises(Exception):
            tarefa1.adicionar_tarefa("Tarefa 1" / 0)