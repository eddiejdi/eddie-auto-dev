# Importações necessárias
import argparse

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        for i, tarefa in enumerate(self.tarefas, 1):
            print(f"{i}. {tarefa}")

    def remover_tarefa(self, indice):
        if 0 < indice <= len(self.tarefas):
            del self.tarefas[indice - 1]
        else:
            print("Índice inválido")

def main():
    parser = argparse.ArgumentParser(description="Tarefa 1")
    parser.add_argument("--adicionar", help="Adicionar uma tarefa")
    parser.add_argument("--listar", action="store_true", help="Listar todas as tarefas")
    parser.add_argument("--remover", type=int, help="Remover uma tarefa pelo índice")

    args = parser.parse_args()

    if args.adicionar:
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(args.adicionar)
        print("Tarefa adicionada com sucesso!")

    if args.listar:
        tarefa1 = Tarefa1()
        tarefa1.listar_tarefas()

    if args.remover:
        tarefa1 = Tarefa1()
        tarefa1.remover_tarefa(args.remover)

if __name__ == "__main__":
    main()