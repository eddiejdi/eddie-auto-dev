import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome

    def executar(self):
        print(f"Executando tarefa: {self.nome}")

def main():
    try:
        # Criar uma instância da classe Tarefa
        tarefa1 = Tarefa("Tarefa 1")

        # Executar a tarefa
        tarefa1.executar()

    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()