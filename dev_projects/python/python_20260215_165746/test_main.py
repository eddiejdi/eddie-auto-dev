import pytest
from src.tarefa import Tarefa
from src.tarefaservice import TarefaService

def test_tarefa_init():
    tarefa = Tarefa(1, "Tarefa 1", "Descrição da Tarefa 1")
    assert tarefa.id == 1
    assert tarefa.nome == "Tarefa 1"
    assert tarefa.descricao == "Descrição da Tarefa 1"

def test_tarefa_to_json():
    tarefa = Tarefa(1, "Tarefa 1", "Descrição da Tarefa 1")
    json_data = tarefa.to_json()
    expected_json = '{"id": 1, "nome": "Tarefa 1", "descricao": "Descrição da Tarefa 1"}'
    assert json_data == expected_json

def test_tarefaservice_init():
    service = TarefaService()
    assert len(service.tarefas) == 0

def test_tarefaservice_add_task():
    service = TarefaService()
    tarefa = Tarefa(1, "Tarefa 1", "Descrição da Tarefa 1")
    service.adicionar_tarefa(tarefa)
    assert len(service.tarefas) == 1
    assert service.tarefas[0].id == 1

def test_tarefaservice_list_tasks():
    service = TarefaService()
    tarefa1 = Tarefa(1, "Tarefa 1", "Descrição da Tarefa 1")
    tarefa2 = Tarefa(2, "Tarefa 2", "Descrição da Tarefa 2")
    service.adicionar_tarefa(tarefa1)
    service.adicionar_tarefa(tarefa2)
    expected_tasks = [tarefa1.to_json(), tarefa2.to_json()]
    assert service.listar_tarefas() == expected_tasks

def test_tarefaservice_remove_task():
    service = TarefaService()
    tarefa1 = Tarefa(1, "Tarefa 1", "Descrição da Tarefa 1")
    tarefa2 = Tarefa(2, "Tarefa 2", "Descrição da Tarefa 2")
    service.adicionar_tarefa(tarefa1)
    service.adicionar_tarefa(tarefa2)
    service.remover_tarefa(1)
    assert len(service.tarefas) == 1
    assert service.tarefas[0].id == 2

def test_tarefaservice_list_tasks_edge_cases():
    service = TarefaService()
    expected_tasks = []
    assert service.listar_tarefas() == expected_tasks