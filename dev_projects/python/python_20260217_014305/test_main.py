import pytest
from unittest.mock import patch
from tarefa1 import Tarefa1

def test_add_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Fazer compras")
    assert "Fazer compras" in tarefa1.tarefas, "Tarefa não adicionada corretamente"

def test_remove_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Fazer compras")
    tarefa1.remove_tarefa("Fazer compras")
    assert len(tarefa1.tarefas) == 0, "Tarefa não removida corretamente"

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Fazer compras")
    tarefa1.add_tarefa("Levar ao cinema")
    assert sorted(tarefa1.listar_tarefas()) == ["Fazer compras", "Levar ao cinema"], "Lista de tarefas incorreta"

def test_sortear_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.add_tarefa("Fazer compras")
    tarefa1.add_tarefa("Levar ao cinema")
    tarefa1.add_tarefa("Estudar Python")

    with patch('random.shuffle') as mock_shuffle:
        mock_shuffle.return_value = ["Levar ao cinema", "Fazer compras", "Estudar Python"]
        sorteada = tarefa1.sortear_tarefa()
        assert sorteada in ["Levar ao cinema", "Fazer compras", "Estudar Python"], "Tarefa não sorteada corretamente"

def test_remove_tarefa_not_found():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError) as e:
        tarefa1.remove_tarefa("NãoExiste")
    assert str(e.value) == "Tarefa 'NãoExiste' não encontrada", "Erro incorreto ao remover tarefa"

def test_add_tarefa_invalid_type():
    tarefa1 = Tarefa1()
    with pytest.raises(TypeError) as e:
        tarefa1.add_tarefa(123)
    assert str(e.value) == "Tarefa deve ser uma string", "Erro incorreto ao adicionar tarefa"