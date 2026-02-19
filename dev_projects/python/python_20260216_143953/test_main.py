import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if tarefa in self.tarefas:
            raise ValueError("Tarefa já existente")
        self.tarefas.append(tarefa)

    def remover_tarefa(self, tarefa):
        if tarefa not in self.tarefas:
            raise ValueError("Tarefa não encontrada")
        self.tarefas.remove(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def salvar_tarefas(self, arquivo):
        with open(arquivo, 'w') as file:
            for tarefa in self.tarefas:
                file.write(f"{tarefa}\n")

    def carregar_tarefas(self, arquivo):
        try:
            with open(arquivo, 'r') as file:
                self.tarefas = [linha.strip() for linha in file]
        except FileNotFoundError:
            pass

class TestTarefa1:
    def test_adicionar_tarefa(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        assert "Tarefa 1" in tarefa1.tarefas

    def test_remover_tarefa(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.remover_tarefa("Tarefa 1")
        assert len(tarefa1.tarefas) == 0

    def test_listar_tarefas(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.adicionar_tarefa("Tarefa 2")
        assert tarefa1.listar_tarefas() == ["Tarefa 1", "Tarefa 2"]

    def test_salvar_tarefas(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.salvar_tarefas("tarefas.txt")
        with open("tarefas.txt", 'r') as file:
            assert "Tarefa 1" in file.read()

    def test_carregar_tarefas(self, tarefa1):
        # Caso de sucesso com valores válidos
        tarefa1.adicionar_tarefa("Tarefa 1")
        tarefa1.carregar_tarefas("tarefas.txt")
        assert tarefa1.listar_tarefas() == ["Tarefa 1"]

    def test_adicionar_tarefa_existe(self, tarefa1):
        # Caso de erro (tarefa já existente)
        with pytest.raises(ValueError) as excinfo:
            tarefa1.adicionar_tarefa("Tarefa 1")
        assert str(excinfo.value) == "Tarefa já existente"

    def test_remover_tarefa_nao_existe(self, tarefa1):
        # Caso de erro (tarefa não encontrada)
        with pytest.raises(ValueError) as excinfo:
            tarefa1.remover_tarefa("Tarefa 2")
        assert str(excinfo.value) == "Tarefa não encontrada"

    def test_salvar_tarefas_nao_existe(self, tarefa1):
        # Caso de erro (arquivo não existe)
        with pytest.raises(FileNotFoundError):
            tarefa1.salvar_tarefas("tarefas.txt")

    def test_carregar_tarefas_nao_existe(self, tarefa1):
        # Caso de erro (arquivo não existe)
        with pytest.raises(FileNotFoundError):
            tarefa1.carregar_tarefas("tarefas.txt")