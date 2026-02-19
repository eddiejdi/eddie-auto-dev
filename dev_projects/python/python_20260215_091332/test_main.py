import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Entender o que é Python")
    assert "Entender o que é Python" in tarefa1.tarefas

def test_adicionar_tarefa_invalido():
    with pytest.raises(ValueError):
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(20)

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Entender o que é Python")
    assert "Entender o que é Python" in tarefa1.listar_tarefas()

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Entender o que é Python")
    tarefa1.remover_tarefa("Entender o que é Python")
    assert not tarefa1.tarefas

def test_remover_tarefa_inexistente():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa("Não Existe")

def test_listar_vazia():
    tarefa1 = Tarefa1()
    assert tarefa1.listar_tarefas() == []