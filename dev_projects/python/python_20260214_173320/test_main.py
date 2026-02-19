import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        assert "Fazer compras" in tarefa1.tarefas, "Tarefa não adicionada corretamente"

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Estudar Python")
        assert ["Fazer compras", "Estudar Python"] == tarefa1.listar_tarefas(), "Lista de tarefas incorreta"

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.remover_tarefa(0)
        assert "Estudar Python" in tarefa1.tarefas, "Tarefa não removida corretamente"

    def test_salvar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.salvar_tarefas("tarefas.txt")
        with open("tarefas.txt", 'r') as file:
            assert "Fazer compras\n" in file.read(), "Tarefas não salvas corretamente"
            assert "Estudar Python\n" in file.read(), "Tarefas não salvas corretamente"

    def test_carregar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Estudar Python")
        tarefa1.salvar_tarefas("tarefas.txt")
        tarefa1.carregar_tarefas("tarefas.txt")
        assert ["Fazer compras", "Estudar Python"] == tarefa1.listar_tarefas(), "Tarefas não carregadas corretamente"

    def test_adicionar_tarefa_string_invalida(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError) as excinfo:
            tarefa1.adicionar_tarefa(123)
        assert str(excinfo.value) == "Tarefa deve ser uma string", "Erro incorreto"

    def test_remover_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        with pytest.raises(IndexError) as excinfo:
            tarefa1.remover_tarefa(2)
        assert str(excinfo.value) == "Índice inválido", "Erro incorreto"

    def test_salvar_tarefas_arquivo_inexistente(self):
        tarefa1 = Tarefa1()
        with pytest.raises(FileNotFoundError):
            tarefa1.salvar_tarefas("tarefas.txt")

    def test_carregar_tarefas_arquivo_inexistente(self):
        tarefa1 = Tarefa1()
        with pytest.raises(FileNotFoundError):
            tarefa1.carregar_tarefas("tarefas.txt")