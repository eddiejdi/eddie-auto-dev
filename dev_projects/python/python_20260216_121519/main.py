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
        return "\n".join(self.tarefas)

    def remover_tarefa(self, indice):
        if 0 <= indice < len(self.tarefas):
            del self.tarefas[indice]
        else:
            raise IndexError("Índice inválido")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tarefa 1")
    parser.add_argument("opcao", choices=["adicionar", "listar", "remover"], help="Opção a ser executada")
    parser.add_argument("parametro", nargs="?", help="Parâmetro para a opção")

    args = parser.parse_args()

    tarefa1 = Tarefa1()

    if args.opcao == "adicionar":
        if args.parametro:
            tarefa1.adicionar_tarefa(args.parametro)
            print(f"Tarefa '{args.parametro}' adicionada com sucesso.")
        else:
            print("Parâmetro obrigatório para adicionar uma tarefa.")

    elif args.opcao == "listar":
        print(tarefa1.listar_tarefas())

    elif args.opcao == "remover":
        if args.parametro:
            try:
                indice = int(args.parametro)
                tarefa1.remover_tarefa(indice)
                print(f"Tarefa removida com sucesso.")
            except ValueError:
                print("Índice deve ser um número inteiro.")
        else:
            print("Parâmetro obrigatório para remover uma tarefa.")

    else:
        print("Opção inválida.")