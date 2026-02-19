import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.listar_tarefas()

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    assert ["Tarefa 1", "Tarefa 2"] == tarefa1.listar_tarefas()

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    tarefa1.remover_tarefa(0)
    assert "Tarefa 2" in tarefa1.listar_tarefas()

def test_gerar_numeros_aleatorios():
    tarefa1 = Tarefa1()
    numeros = tarefa1.gerar_numeros_aleatorios(5)
    assert len(numeros) == 5
    for num in numeros:
        assert 0 < num <= 100

def test_remover_tarefa_indice_invalido():
    tarefa1 = Tarefa1()
    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(2)

def test_gerar_numeros_aleatorios_divisao_zero():
    tarefa1 = Tarefa1()
    with pytest.raises(ValueError):
        tarefa1.gerar_numeros_aleatorios(0)