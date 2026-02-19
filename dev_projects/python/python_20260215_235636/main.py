# Importações necessárias
import sys

class Tarefa1:
    def __init__(self):
        self.items = []

    def adicionar_item(self, item):
        if not isinstance(item, str):
            raise ValueError("O item deve ser uma string")
        self.items.append(item)

    def remover_item(self, index):
        if not isinstance(index, int) or index < 0:
            raise IndexError("O índice deve ser um número inteiro positivo")
        if index >= len(self.items):
            raise IndexError("Índice fora do alcance da lista")
        del self.items[index]

    def listar_itens(self):
        return self.items

    def salvar_itens(self, arquivo):
        try:
            with open(arquivo, 'w') as file:
                for item in self.items:
                    file.write(item + '\n')
            print(f"Lista salva em {arquivo}")
        except Exception as e:
            print(f"Erro ao salvar lista: {e}")

    def carregar_itens(self, arquivo):
        try:
            with open(arquivo, 'r') as file:
                self.items = [line.strip() for line in file]
            print("Lista carregada com sucesso")
        except FileNotFoundError:
            print("Arquivo não encontrado")
        except Exception as e:
            print(f"Erro ao carregar lista: {e}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    # Exemplos de uso
    tarefa1.adicionar_item("Item 1")
    tarefa1.adicionar_item("Item 2")
    tarefa1.remover_item(0)
    print(tarefa1.listar_itens())
    tarefa1.salvar_itens("tarefas.txt")
    tarefa1.carregar_itens("tarefas.txt")