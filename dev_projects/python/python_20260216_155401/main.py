# Importações necessárias
import random

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, indice):
        if not isinstance(indice, int) or indice < 0:
            raise IndexError("Índice inválido")
        if indice >= len(self.tarefas):
            raise ValueError("Índice fora do alcance")
        del self.tarefas[indice]

    def embaralhar_tarefas(self):
        random.shuffle(self.tarefas)

# Função principal para execução do programa
def main():
    tarefa1 = Tarefa1()
    
    while True:
        print("\nTAREFAS:")
        for i, tarefa in enumerate(tarefa1.listar_tarefas(), start=1):
            print(f"{i}. {tarefa}")
        
        opcao = input("Digite uma opção (A para adicionar, R para remover, E para embaralhar, S para sair): ")
        
        if opcao.upper() == 'A':
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao.upper() == 'R':
            indice = int(input("Digite o índice da tarefa a remover: "))
            try:
                tarefa1.remover_tarefa(indice - 1)  # Subtrai 1 para ajustar o índice
            except ValueError as e:
                print(e)
        elif opcao.upper() == 'E':
            tarefa1.embaralhar_tarefas()
        elif opcao.upper() == 'S':
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()