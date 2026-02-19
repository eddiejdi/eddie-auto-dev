import argparse

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tarefa 1")
    parser.add_argument("--adicionar", type=str, help="Adicionar uma tarefa")
    parser.add_argument("--listar", action="store_true", help="Listar todas as tarefas")
    parser.add_argument("--remover", type=int, help="Remover uma tarefa pelo índice")

    args = parser.parse_args()

    tarefa1 = Tarefa1()

    if args.adicionar:
        tarefa1.adicionar_tarefa(args.adicionar)
        print(f"Tarefa '{args.adicionar}' adicionada com sucesso.")

    if args.listar:
        print("Tarefas:")
        for index, tarefa in enumerate(tarefa1.listar_tarefas()):
            print(f"{index + 1}. {tarefa}")

    if args.remover:
        try:
            tarefa1.remover_tarefa(args.remover - 1)
            print(f"Tarefa removida com sucesso.")
        except IndexError as e:
            print(e)