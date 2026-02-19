import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome

    def executar(self):
        try:
            print(f"Executando tarefa: {self.nome}")
        except Exception as e:
            print(f"Erro ao executar tarefa: {e}")

def main():
    tarefas = [
        Tarefa("Tarefa 1"),
        Tarefa("Tarefa 2")
    ]

    for tarefa in tarefas:
        tarefa.executar()

if __name__ == "__main__":
    main()