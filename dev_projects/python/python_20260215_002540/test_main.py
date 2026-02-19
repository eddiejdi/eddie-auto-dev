import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Task 1")
    assert len(tarefa1.tarefas) == 1, "Tarefa não adicionada corretamente."

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Task 1")
    tarefa1.adicionar_tarefa("Task 2")
    assert tarefa1.listar_tarefas() == ["Task 1", "Task 2"], "Lista de tarefas incorreta."

def test_completar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Task 1")
    tarefa1.completar_tarefa(0)
    assert len(tarefa1.tarefas) == 0, "Tarefa não completada corretamente."

def test_gerar_tarefa_randomica():
    tarefa1 = Tarefa1()
    tarefa1.gerar_tarefa_randomica(3)
    assert len(tarefa1.tarefas) == 3, "Quantidade de tarefas incorreta."