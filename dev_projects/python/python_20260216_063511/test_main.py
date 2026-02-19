import pytest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)
        print(f"Tarefa '{tarefa}' adicionada.")

    def listar_tarefas(self):
        if not self.tarefas:
            print("Nenhuma tarefa para listar.")
        else:
            print("Tarefas:")
            for i, tarefa in enumerate(self.tarefas, 1):
                print(f"{i}. {tarefa}")

    def remover_tarefa(self, indice):
        try:
            del self.tarefas[indice - 1]
            print(f"Tarefa removida.")
        except IndexError:
            print("Índice inválido. Tente novamente.")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    # Casos de sucesso
    tarefa1.adicionar_tarefa("Tarefa 1")
    assert tarefa1.tarefas == ["Tarefa 1"], "Adição de tarefa falhou."

    tarefa1.listar_tarefas()
    assert tarefa1.tarefas == ["Tarefa 1"], "Listagem de tarefas falhou."

    # Casos de erro
    with pytest.raises(ValueError):
        tarefa1.adicionar_tarefa("")

    with pytest.raises(IndexError):
        tarefa1.remover_tarefa(0)

    # Edge cases
    tarefa1.listar_tarefas()
    assert tarefa1.tarefas == ["Tarefa 1"], "Listagem de tarefas falhou."

    tarefa1.adicionar_tarefa("Tarefa 2")
    assert tarefa1.tarefas == ["Tarefa 1", "Tarefa 2"], "Adição de tarefa falhou."

    tarefa1.remover_tarefa(1)
    assert tarefa1.tarefas == ["Tarefa 1"], "Remoção de tarefa falhou."