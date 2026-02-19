# Importações necessárias
import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []
    
    def adicionar_tarefa(self, tarefa):
        # Adiciona uma nova tarefa à lista
        self.tarefas.append(tarefa)
    
    def listar_tarefas(self):
        # Lista todas as tarefas disponíveis
        return self.tarefas
    
    def remover_tarefa(self, indice):
        # Remove uma tarefa pelo índice
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
    
    def gerar_tarefa_randomica(self):
        # Gera uma nova tarefa aleatória
        return f"Tarefa {random.randint(1, 100)}"

if __name__ == "__main__":
    tarefa = Tarefa1()
    
    # Adicionando algumas tarefas
    tarefa.adicionar_tarefa("Entregar projeto")
    tarefa.adicionar_tarefa("Lavar o carro")
    
    # Listando todas as tarefas
    print("Tarefas disponíveis:")
    for i, tarefa in enumerate(tarefa.listar_tarefas()):
        print(f"{i+1}. {tarefa}")
    
    # Removendo uma tarefa
    indice = 0  # Primeira tarefa
    tarefa.remover_tarefa(indice)
    print("Tarefas após remoção:")
    for i, tarefa in enumerate(tarefa.listar_tarefas()):
        print(f"{i+1}. {tarefa}")
    
    # Gerando uma nova tarefa aleatória
    nova_tarefa = tarefa.gerar_tarefa_randomica()
    print("Nova tarefa gerada:", nova_tarefa)