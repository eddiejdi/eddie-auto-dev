import pytest

class Tarefa1:
    def __init__(self, nome):
        self.nome = nome
        self.status = "Pendente"

    def marcar_completa(self):
        self.status = "Completa"

    def __str__(self):
        return f"Tarefa: {self.nome}, Status: {self.status}"

def listar_tarefas(tarefas):
    for tarefa in tarefas:
        print(tarefa)

def main():
    # Criando uma lista de tarefas
    tarefas = [Tarefa1("Revisar código"), Tarefa1("Entregar projeto")]

    while True:
        print("\nMenu:")
        print("1. Listar tarefas")
        print("2. Marcar tarefa como completa")
        print("3. Sair")

        opcao = input("Digite a opção (1/2/3): ")

        if opcao == "1":
            listar_tarefas(tarefas)
        elif opcao == "2":
            nome_tarefa = input("Digite o nome da tarefa para marcar como completa: ")
            for tarefa in tarefas:
                if tarefa.nome == nome_tarefa:
                    tarefa.marcar_completa()
                    print(f"Tarefa '{nome_tarefa}' marcada como completa.")
                    break
            else:
                print("Tarefa não encontrada.")
        elif opcao == "3":
            print("Saindo do programa...")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()