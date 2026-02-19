import pytest
from main import TarefaManager, add_tarefa, list_tarefas, marcar_tarefa_completa

def test_add_tarefa():
    manager = TarefaManager()
    tarefa = Tarefa("Tarefa 1")
    manager.adicionar_tarefa(tarefa)
    assert len(manager.tarefas) == 1
    assert manager.tarefas[0].nome == "Tarefa 1"

def test_list_tarefas():
    manager = TarefaManager()
    tarefa1 = Tarefa("Tarefa 1")
    tarefa2 = Tarefa("Tarefa 2")
    manager.adicionar_tarefa(tarefa1)
    manager.adicionar_tarefa(tarefa2)
    list_tarefas(manager)
    assert "Tarefa 1" in sys.stdout.getvalue()
    assert "Tarefa 2" in sys.stdout.getvalue()

def test_marcar_tarefa_completa():
    manager = TarefaManager()
    tarefa = Tarefa("Tarefa 1")
    manager.adicionar_tarefa(tarefa)
    marcar_tarefa_completa(manager, "Tarefa 1")
    assert tarefa.status == "concluída"

def test_marcar_tarefa_completa_error():
    manager = TarefaManager()
    marcar_tarefa_completa(manager, "Tarefa Inexistente")

def test_add_tarefa_error():
    manager = TarefaManager()
    add_tarefa(manager, "123")  # Valor inválido

def test_list_tarefas_error():
    manager = TarefaManager()
    list_tarefas(manager)  # Nenhuma tarefa adicionada