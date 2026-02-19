import argparse

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        for i, tarefa in enumerate(self.tarefas, start=1):
            print(f"{i}. {tarefa}")

    def remover_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
            print("Tarefa removida.")
        else:
            print("Índice inválido.")

def main():
    parser = argparse.ArgumentParser(description="CLI para gerenciamento de tarefas")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser para adicionar tarefa
    add_parser = subparsers.add_parser("add", help="Adicionar uma nova tarefa")
    add_parser.add_argument("tarefa", type=str, help="Tarefa a ser adicionada")
    add_parser.set_defaults(func=Tarefa1().adicionar_tarefa)

    # Subparser para listar tarefas
    list_parser = subparsers.add_parser("list", help="Listar todas as tarefas")
    list_parser.set_defaults(func=Tarefa1().listar_tarefas)

    # Subparser para remover tarefa
    remove_parser = subparsers.add_parser("remove", help="Remover uma tarefa pelo índice")
    remove_parser.add_argument("indice", type=int, help="Índice da tarefa a ser removida")
    remove_parser.set_defaults(func=Tarefa1().remover_tarefa)

    args = parser.parse_args()

    if hasattr(args, "func"):
        try:
            args.func(args.tarefa)
        except Exception as e:
            print(f"Erro: {e}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()