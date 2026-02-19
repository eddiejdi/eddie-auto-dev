import pytest
from typing import List

class Tarefa:
    def __init__(self, id: int, nome: str):
        self.id = id
        self.nome = nome
        self.status = "pendente"

    def marcar_completa(self):
        self.status = "completa"

def listar_tarefas(tarefas: List[Tarefa]) -> None:
    for tarefa in tarefas:
        print(f"{tarefa.id}: {tarefa.nome} - Status: {tarefa.status}")

def criar_tarefa(id: int, nome: str) -> Tarefa:
    return Tarefa(id, nome)

def main() -> None:
    try:
        tarefas = []
        
        # Criar algumas tarefas
        t1 = criar_tarefa(1, "Tarefa 1")
        t2 = criar_tarefa(2, "Tarefa 2")
        
        # Adicionar às tarefas
        tarefas.append(t1)
        tarefas.append(t2)
        
        # Listar todas as tarefas
        listar_tarefas(tarefas)
        
        # Marcar uma tarefa como completa
        t1.marcar_completa()
        
        # Listar novamente para confirmar a atualização
        listar_tarefas(tarefas)
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()

# Testes unitários

def test_listar_tarefas():
    tarefas = [Tarefa(1, "Tarefa 1"), Tarefa(2, "Tarefa 2")]
    listar_tarefas(tarefas)
    assert "1: Tarefa 1 - Status: pendente" in stdout.getvalue()
    assert "2: Tarefa 2 - Status: pendente" in stdout.getvalue()

def test_listar_tarefas_completa():
    tarefas = [Tarefa(1, "Tarefa 1"), Tarefa(2, "Tarefa 2")]
    tarefas[0].marcar_completa()
    listar_tarefas(tarefas)
    assert "1: Tarefa 1 - Status: completa" in stdout.getvalue()

def test_listar_tarefas_vazia():
    listar_tarefas([])
    assert "" in stdout.getvalue()

def test_listar_tarefas_string_vazia():
    listar_tarefas([""])
    assert "" in stdout.getvalue()

def test_listar_tarefas_none():
    listar_tarefas(None)
    assert "" in stdout.getvalue()

def test_listar_tarefas_divisao_por_zero():
    with pytest.raises(ZeroDivisionError):
        listar_tarefas([1, 0])