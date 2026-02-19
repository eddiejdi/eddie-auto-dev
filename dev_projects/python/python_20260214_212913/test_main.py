import pytest
from tarefa1 import Tarefa1

def test_adicionar_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o café")
    assert "Lavar o café" in tarefa1.tarefas, "Tarefa não adicionada corretamente"

def test_listar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o café")
    tarefa1.adicionar_tarefa("Estudar Python")
    assert ["Lavar o café", "Estudar Python"] == tarefa1.listar_tarefas(), "Lista de tarefas incorreta"

def test_remover_tarefa():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o café")
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.remover_tarefa(0)
    assert "Estudar Python" in tarefa1.tarefas, "Tarefa removida incorretamente"

def test_salvar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o café")
    tarefa1.salvar_tarefas()
    assert os.path.exists("tarefas.txt"), "Arquivo não criado corretamente"
    with open("tarefas.txt", "r") as file:
        content = file.read().strip()
    assert "Lavar o café" in content, "Conteúdo do arquivo incorreto"

def test_carregar_tarefas():
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Lavar o café")
    tarefa1.salvar_tarefas()
    tarefa1.carregar_tarefas()
    assert "Lavar o café" in tarefa1.tarefas, "Tarefas carregadas incorretamente"