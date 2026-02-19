# Importações necessárias
import os

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
        if index < 0 or index >= len(self.tarefas):
            raise IndexError("Índice de tarefa inválido")
        del self.tarefas[index]

    def salvar_tarefas(self, arquivo):
        with open(arquivo, 'w') as file:
            for tarefa in self.tarefas:
                file.write(f"{tarefa}\n")

    def carregar_tarefas(self, arquivo):
        if not os.path.exists(arquivo):
            raise FileNotFoundError("Arquivo de tarefas não encontrado")
        with open(arquivo, 'r') as file:
            for linha in file:
                self.adicionar_tarefa(linha.strip())

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    
    # Adicionar tarefas
    tarefa1.adicionar_tarefa("Lavar o café")
    tarefa1.adicionar_tarefa("Estudar Python")
    tarefa1.adicionar_tarefa("Ir ao supermercado")
    
    # Listar tarefas
    print(tarefa1.listar_tarefas())
    
    # Remover tarefa
    tarefa1.remover_tarefa(1)
    
    # Salvar tarefas em arquivo
    tarefa1.salvar_tarefas("tarefas.txt")
    
    # Carregar tarefas do arquivo
    tarefa1.carregar_tarefas("tarefas.txt")
    
    print(tarefa1.listar_tarefas())