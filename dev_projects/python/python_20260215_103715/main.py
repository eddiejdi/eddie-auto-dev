from typing import List

class Tarefa1:
    def __init__(self):
        self.tarefas: List[str] = []

    def adicionar_tarefa(self, tarefa: str) -> None:
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self) -> List[str]:
        return self.tarefas

    def remover_tarefa(self, index: int) -> None:
        if not isinstance(index, int):
            raise ValueError("Índice deve ser um inteiro")
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice fora do alcance da lista")
        del self.tarefas[index]

    def __str__(self) -> str:
        return f"Tarefa1(tarefas={self.tarefas})"

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.adicionar_tarefa("Tarefa 1")
    tarefa1.adicionar_tarefa("Tarefa 2")
    print(tarefa1)
    print(tarefa1.listar_tarefas())
    tarefa1.remover_tarefa(0)
    print(tarefa1)