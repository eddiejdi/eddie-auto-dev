import argparse

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if not isinstance(tarefa, str):
            raise ValueError("Tarefa deve ser uma string")
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return "\n".join(self.tarefas)

    def remover_tarefa(self, index):
        try:
            del self.tarefas[index]
        except IndexError:
            raise ValueError("Índice inválido")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tarefa 1")
    parser.add_argument("--adicionar", help="Adicionar uma tarefa")
    parser.add_argument("--listar", action="store_true", help="Listar todas as tarefas")
    parser.add_argument("--remover", type=int, help="Remover uma tarefa pelo índice")

    args = parser.parse_args()

    tarefa1 = Tarefa1()

    if args.adicionar:
        tarefa1.adicionar_tarefa(args.adicionar)
        print("Tarefa adicionada:", args.adicionar)

    if args.listar:
        print("Tarefas:")
        print(tarefa1.listar_tarefas())

    if args.remover is not None:
        try:
            tarefa1.remover_tarefa(args.remover)
            print(f"Tarefa removida: {args.remover}")
        except ValueError as e:
            print(e)