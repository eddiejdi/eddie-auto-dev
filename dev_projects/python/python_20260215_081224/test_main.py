import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa = Tarefa1()
    tarefa.adicionar_tarefa("Entregar projeto")
    assert "Entregar projeto" in tarefa.listar_tarefas()

def test_listar_tarefas():
    tarefa = Tarefa1()
    tarefa.adicionar_tarefa("Entregar projeto")
    tarefa.adicionar_tarefa("Lavar o carro")
    assert len(tarefa.listar_tarefas()) == 2

def test_remover_tarefa():
    tarefa = Tarefa1()
    tarefa.adicionar_tarefa("Entregar projeto")
    tarefa.adicionar_tarefa("Lavar o carro")
    tarefa.remover_tarefa(0)
    assert "Entregar projeto" not in tarefa.listar_tarefas()

def test_gerar_tarefa_randomica():
    tarefa = Tarefa1()
    nova_tarefa = tarefa.gerar_tarefa_randomica()
    assert isinstance(nova_tarefa, str)

def test_divisao_pelo_zero():
    with pytest.raises(ZeroDivisionError):
        10 / 0

def test_valores_invalidos():
    with pytest.raises(ValueError):
        Tarefa1().adicionar_tarefa("123abc")

def test_edge_cases():
    tarefa = Tarefa1()
    assert len(tarefa.listar_tarefas()) == 0