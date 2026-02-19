import pytest

class TestTarefa1:
    def test_adicionar_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        assert "Fazer compras" in tarefa1.tarefas, "Tarefa não adicionada corretamente"

    def test_adicionar_tarefa_invalido(self):
        with pytest.raises(ValueError) as e:
            Tarefa1().adicionar_tarefa(123)
        assert str(e.value) == "Tarefa deve ser uma string", "Erro incorreto na adição de tarefa"

    def test_listar_tarefas(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Leitura")
        assert tarefa1.listar_tarefas() == ["Fazer compras", "Leitura"], "Lista de tarefas incorreta"

    def test_listar_tarefas_vazia(self):
        tarefa1 = Tarefa1()
        assert tarefa1.listar_tarefas() == [], "Lista de tarefas vazia incorreta"

    def test_remover_tarefa(self):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa("Fazer compras")
        tarefa1.adicionar_tarefa("Leitura")
        tarefa1.remover_tarefa(0)
        assert "Leitura" in tarefa1.tarefas, "Tarefa removida incorretamente"

    def test_remover_tarefa_indice_invalido(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError) as e:
            tarefa1.remover_tarefa(2)
        assert str(e.value) == "Índice inválido", "Erro incorreto na remoção de tarefa"

    def test_remover_tarefa_indice_negativo(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError) as e:
            tarefa1.remover_tarefa(-1)
        assert str(e.value) == "Índice inválido", "Erro incorreto na remoção de tarefa"

    def test_remover_tarefa_indice_excedente(self):
        tarefa1 = Tarefa1()
        with pytest.raises(IndexError) as e:
            tarefa1.remover_tarefa(3)
        assert str(e.value) == "Índice inválido", "Erro incorreto na remoção de tarefa"