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

    def remover_tarefa(self, indice):
        if not isinstance(indice, int) or indice < 0 or indice >= len(self.tarefas):
            raise IndexError("Índice inválido")
        del self.tarefas[indice]

    def salvar_tarefas(self, arquivo):
        with open(arquivo, 'w') as file:
            for tarefa in self.tarefas:
                file.write(tarefa + '\n')

    def carregar_tarefas(self, arquivo):
        try:
            with open(arquivo, 'r') as file:
                self.tarefas = [linha.strip() for linha in file.readlines()]
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    while True:
        print("\nMenu:")
        print("1. Adicionar Tarefa")
        print("2. Listar Tarefas")
        print("3. Remover Tarefa")
        print("4. Salvar Tarefas")
        print("5. Carregar Tarefas")
        print("6. Sair")

        opcao = input("Escolha uma opção: ")

        if opcao == '1':
            tarefa = input("Digite a nova tarefa: ")
            tarefa1.adicionar_tarefa(tarefa)
        elif opcao == '2':
            print("\nTarefas:")
            for i, tarefa in enumerate(tarefa1.listar_tarefas()):
                print(f"{i+1}. {tarefa}")
        elif opcao == '3':
            indice = int(input("Digite o índice da tarefa a remover: "))
            tarefa1.remover_tarefa(indice)
        elif opcao == '4':
            arquivo = input("Digite o nome do arquivo para salvar as tarefas: ")
            tarefa1.salvar_tarefas(arquivo)
        elif opcao == '5':
            arquivo = input("Digite o nome do arquivo para carregar as tarefas: ")
            tarefa1.carregar_tarefas(arquivo)
        elif opcao == '6':
            print("Saindo...")
            sys.exit(0)
        else:
            print("Opção inválida. Tente novamente.")