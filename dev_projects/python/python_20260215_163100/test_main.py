import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 'Tarefa 1' adicionada com sucesso." in tarefa1.tarefas[0]

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.listar_tarefas()
    assert "Tarefas:" in tarefa1.tarefas[0]
    assert "1. Tarefa 1" in tarefa1.tarefas[0]

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.remover_tarefa(1)
    assert "Nenhuma tarefa encontrada." in tarefa1.tarefas[0]

def test_buscar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.buscar_tarefa("tarefa")
    assert "Tarefas encontradas:" in tarefa1.tarefas[0]
    assert "1. Tarefa 1" in tarefa1.tarefas[0]

def test_adicionar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa(123)

def test_listar_tarefas_vazia():
    tarefa1 = Tarefa1()
    tarefa1.listar_tarefas()
    assert "Nenhuma tarefa encontrada." in tarefa1.tarefas[0]

def test_remover_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.remover_tarefa(0)

def test_buscar_tarefa_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.buscar_tarefa("tarefa")

def test_adicionar_tarefa_divisao_zero():
    tarefa1 = Tarefa1()
    with pytest.raises(Exception):
        tarefa1.adicionar_tarefa("Tarefa 1" / 0)

def test_listar_tarefas_divisao_zero():
    tarefa1 = Tarefa1()
    with pytest.raises(Exception):
        tarefa1.listar_tarefas() / 0

def test_remover_tarefa_divisao_zero():
    tarefa1 = Tarefa1()
    with pytest.raises(Exception):
        tarefa1.remover_tarefa(1) / 0

def test_buscar_tarefa_divisao_zero():
    tarefa1 = Tarefa1()
    with pytest.raises(Exception):
        tarefa1.buscar_tarefa("tarefa") / 0