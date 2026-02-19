import argparse

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        if not self.tarefas:
            print("Nenhuma tarefa adicionada.")
        else:
            for i, tarefa in enumerate(self.tarefas, start=1):
                print(f"{i}. {tarefa}")

    def remover_tarefa(self, indice):
        try:
            del self.tarefas[indice - 1]
            print("Tarefa removida com sucesso.")
        except IndexError:
            print("Índice inválido.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerenciador de tarefas")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser para adicionar tarefa
    add_parser = subparsers.add_parser("add", help="Adiciona uma nova tarefa")
    add_parser.add_argument("tarefa", type=str, help="Título da tarefa")

    # Subparser para listar tarefas
    list_parser = subparsers.add_parser("list", help="Lista todas as tarefas")

    # Subparser para remover tarefa
    remove_parser = subparsers.add_parser("remove", help="Remove uma tarefa pelo índice")
    remove_parser.add_argument("indice", type=int, help="Índice da tarefa a ser removida")

    args = parser.parse_args()

    if args.command == "add":
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(args.tarefa)
    elif args.command == "list":
        tarefa1 = Tarefa1()
        tarefa1.listar_tarefas()
    elif args.command == "remove":
        tarefa1 = Tarefa1()
        tarefa1.remover_tarefa(args.indice)