import argparse

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
            raise ValueError("Índice deve ser um número inteiro positivo")
        if indice >= len(self.tarefas):
            raise IndexError("Índice fora do alcance da lista")
        del self.tarefas[indice]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tarefa 1 - SCRUM-1")
    parser.add_argument("--adicionar", type=str, help="Adicionar uma nova tarefa")
    parser.add_argument("--listar", action="store_true", help="Listar todas as tarefas")
    parser.add_argument("--remover", type=int, help="Remover uma tarefa pelo índice")

    args = parser.parse_args()

    tarefa1 = Tarefa1()

    if args.adicionar:
        tarefa1.adicionar_tarefa(args.adicionar)
        print(f"Tarefa adicionada: {args.adicionar}")

    if args.listar:
        print("Tarefas:")
        for i, tarefa in enumerate(tarefa1.listar_tarefas()):
            print(f"{i+1}. {tarefa}")

    if args.remover:
        try:
            tarefa1.remover_tarefa(args.remover)
            print(f"Tarefa removida: {args.remover}")
        except IndexError as e:
            print(e)