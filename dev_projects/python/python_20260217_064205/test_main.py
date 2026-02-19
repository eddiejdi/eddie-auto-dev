import pytest
from typing import List

class Tarefa:
    def __init__(self, id: int, nome: str, status: str):
        self.id = id
        self.nome = nome
        self.status = status

    def __str__(self) -> str:
        return f"Tarefa({self.id}, {self.nome}, {self.status})"

class TarefasRepository:
    def __init__(self):
        self.tarefas: List[Tarefa] = []

    def adicionar_tarefa(self, tarefa: Tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self) -> List[Tarefa]:
        return self.tarefas

    def editar_tarefa(self, id: int, novo_status: str):
        for tarefa in self.tarefas:
            if tarefa.id == id:
                tarefa.status = novo_status
                break

    def excluir_tarefa(self, id: int):
        self.tarefas = [tarefa for tarefa in self.tarefas if tarefa.id != id]

class TarefaService:
    def __init__(self, repository: TarefasRepository):
        self.repository = repository

    def criar_tarefa(self, nome: str) -> Tarefa:
        # Implementação para criar uma nova tarefa
        pass

    def listar_tarefas(self) -> List[Tarefa]:
        return self.repository.listar_tarefas()

    def editar_tarefa(self, id: int, novo_status: str):
        self.repository.editar_tarefa(id, novo_status)

    def excluir_tarefa(self, id: int):
        self.repository.excluir_tarefa(id)

def main():
    # Criação do repositório
    repository = TarefasRepository()

    # Criação da serviço
    service = TarefaService(repository)

    # Exemplo de uso das funções
    tarefa1 = service.criar_tarefa("Tarefa 1")
    print(service.listar_tarefas())
    service.editar_tarefa(tarefa1.id, "Concluída")
    print(service.listar_tarefas())
    service.excluir_tarefa(tarefa1.id)
    print(service.listar_tarefas())

if __name__ == "__main__":
    main()