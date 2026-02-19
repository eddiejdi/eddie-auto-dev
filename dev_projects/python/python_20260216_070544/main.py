import argparse

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if isinstance(tarefa, str):
            self.tarefas.append(tarefa)
        else:
            raise ValueError("Tarefa deve ser uma string")

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, tarefa):
        if tarefa in self.tarefas:
            self.tarefas.remove(tarefa)
        else:
            raise ValueError("Tarefa não encontrada")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tarefa 1")
    parser.add_argument("--adicionar", type=str, help="Adicionar uma tarefa")
    parser.add_argument("--listar", action="store_true", help="Listar todas as tarefas")
    parser.add_argument("--remover", type=str, help="Remover uma tarefa")

    args = parser.parse_args()

    tarefa1 = Tarefa1()

    if args.adicionar:
        try:
            tarefa1.adicionar_tarefa(args.adicionar)
            print(f"Tarefa '{args.adicionar}' adicionada com sucesso.")
        except ValueError as e:
            print(e)

    if args.listar:
        print("Tarefas:")
        for tarefa in tarefa1.listar_tarefas():
            print(tarefa)

    if args.remover:
        try:
            tarefa1.remover_tarefa(args.remover)
            print(f"Tarefa '{args.remover}' removida com sucesso.")
        except ValueError as e:
            print(e)