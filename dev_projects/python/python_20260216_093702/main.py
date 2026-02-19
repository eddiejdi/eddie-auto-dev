# Importações necessárias
import sys

class Tarefa1:
    def __init__(self):
        self.tarefas = []
    
    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)
    
    def listar_tarefas(self):
        return self.tarefas
    
    def remover_tarefa(self, index):
        if not isinstance(index, int) or index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[index]
    
    def salvar_tarefas(self, arquivo):
        try:
            with open(arquivo, 'w') as file:
                for tarefa in self.tarefas:
                    file.write(f"{tarefa}\n")
            print(f"Tarefas salvas em {arquivo}")
        except IOError as e:
            print(f"Erro ao salvar tarefas: {e}")

    def carregar_tarefas(self, arquivo):
        try:
            with open(arquivo, 'r') as file:
                self.tarefas = [linha.strip() for linha in file.readlines()]
            print("Tarefas carregadas do arquivo")
        except IOError as e:
            print(f"Erro ao carregar tarefas: {e}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    
    # Exemplo de uso
    tarefa1.adicionar_tarefa("Fazer compras")
    tarefa1.adicionar_tarefa("Levar dinheiro para o banco")
    
    print("Tarefas:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)
    
    tarefa1.remover_tarefa(0)
    
    print("\nTarefas após remoção:")
    for tarefa in tarefa1.listar_tarefas():
        print(tarefa)
    
    tarefa1.salvar_tarefas("tarefas.txt")
    
    carregada = Tarefa1()
    carregada.carregar_tarefas("tarefas.txt")
    
    print("\nTarefas carregadas de volta:")
    for tarefa in carregada.listar_tarefas():
        print(tarefa)