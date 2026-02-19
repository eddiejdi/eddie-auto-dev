import pytest
from tarefa1 import Tarefa1

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        assert "Fazer compras" in tarefa1.tarefas

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Levar ao banco")
        assert tarefa1.listar_tarefas() == ["Fazer compras", "Levar ao banco"]

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Levar ao banco")
        tarefa1.remover_tarefa(0)
        assert "Fazer compras" not in tarefa1.tarefas

    def test_salvar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.salvar_tarefas()
        with open("tarefas.txt", "r") as file:
            assert "Fazer compras" in file.read()

    def test_carregar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.salvar_tarefas()
        tarefa1.carregar_tarefas()
        assert "Fazer compras" in tarefa1.tarefas

    def test_adicionar_tarefa_invalida(self):
        with pytest.raises(ValueError):
            Tarefa1().adicionar_tarefa(123)

    def test_remover_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa(-1)
        with pytest.raises(ValueError):
            tarefa1.remover_tarefa(2)

    def test_salvar_tarefas_arquivo_inexistente(self):
        with pytest.raises(FileNotFoundError):
            Tarefa1().salvar_tarefas("inexistente.txt")

    def test_carregar_tarefas_arquivo_inexistente(self):
        with pytest.raises(FileNotFoundError):
            Tarefa1().carregar_tarefas("inexistente.txt")