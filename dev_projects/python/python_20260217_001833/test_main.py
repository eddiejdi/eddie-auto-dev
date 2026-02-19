import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert "Tarefa 1" in tarefa1.tarefas

def test_marcar_tarefa_concluida():
    tarefa1 = Tarefa1()
    tarefa1.gerar_tarefa_randomica(5)
    index = random.randint(0, len(tarefa1.tarefas) - 1)
    tarefa1.marcar_tarefa_concluida(index)
    assert "Tarefa 1" not in tarefa1.tarefas
    assert "Tarefa 1" in tarefa1.concluidas

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.gerar_tarefa_randomica(5)
    assert len(tarefa1.listar_tarefas()) == 5

def test_listar_concluidas():
    tarefa1 = Tarefa1()
    tarefa1.gerar_tarefa_randomica(5)
    index = random.randint(0, len(tarefa1.tarefas) - 1)
    tarefa1.marcar_tarefa_concluida(index)
    assert len(tarefa1.listar_concluidas()) == 1

def test_gerar_tarefa_randomica():
    tarefa1 = Tarefa1()
    tarefa1.gerar_tarefa_randomica(5)
    assert len(tarefa1.tarefas) == 5