import pytest
from main import Tarefa, TarefaService

def test_add_tarefa():
    service = TarefaService()
    tarefa = Tarefa(1, "Entregar projeto", "Pendente")
    service.add_tarefa(tarefa)
    assert len(service.get_tarefas()) == 1

def test_get_tarefas():
    service = TarefaService()
    tarefa1 = Tarefa(1, "Entregar projeto", "Pendente")
    tarefa2 = Tarefa(2, "Lavar o carro", "Concluído")
    service.add_tarefa(tarefa1)
    service.add_tarefa(tarefa2)
    assert len(service.get_tarefas()) == 2

def test_update_tarefa():
    service = TarefaService()
    tarefa = Tarefa(1, "Entregar projeto", "Pendente")
    service.add_tarefa(tarefa)
    service.update_tarefa(1, descricao="Entregar projeto em tempo limite")
    assert len(service.get_tarefas()) == 1
    updated_tarefa = [t for t in service.get_tarefas() if t.id == 1][0]
    assert updated_tarefa.descricao == "Entregar projeto em tempo limite"

def test_delete_tarefa():
    service = TarefaService()
    tarefa1 = Tarefa(1, "Entregar projeto", "Pendente")
    tarefa2 = Tarefa(2, "Lavar o carro", "Concluído")
    service.add_tarefa(tarefa1)
    service.add_tarefa(tarefa2)
    service.delete_tarefa(2)
    assert len(service.get_tarefas()) == 1

def test_update_tarefa_invalido():
    service = TarefaService()
    tarefa = Tarefa(1, "Entregar projeto", "Pendente")
    service.add_tarefa(tarefa)
    with pytest.raises(ValueError):
        service.update_tarefa(1, descricao="Entregar projeto em tempo limite", status="Invalido")

def test_delete_tarefa_invalido():
    service = TarefaService()
    tarefa1 = Tarefa(1, "Entregar projeto", "Pendente")
    tarefa2 = Tarefa(2, "Lavar o carro", "Concluído")
    service.add_tarefa(tarefa1)
    with pytest.raises(ValueError):
        service.delete_tarefa(2)

def test_get_tarefas_empty():
    service = TarefaService()
    assert len(service.get_tarefas()) == 0