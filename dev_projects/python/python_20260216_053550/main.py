import argparse

class Tarefa:
    def __init__(self, nome):
        self.nome = nome
        self.status = "pendente"

    def marcar_completa(self):
        self.status = "concluída"

    def __str__(self):
        return f"{self.nome} ({self.status})"

class TarefaManager:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        for tarefa in self.tarefas:
            print(tarefa)

    def marcar_tarefa_completa(self, nome_tarefa):
        for tarefa in self.tarefas:
            if tarefa.nome == nome_tarefa:
                tarefa.marcar_completa()
                break

def main():
    parser = argparse.ArgumentParser(description="Tarefa Manager")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser para adicionar uma nova tarefa
    add_parser = subparsers.add_parser("add", help="Adicionar uma nova tarefa")
    add_parser.add_argument("nome", type=str, help="Nome da tarefa")
    add_parser.set_defaults(func=add_tarefa)

    # Subparser para listar todas as tarefas
    list_parser = subparsers.add_parser("list", help="Listar todas as tarefas")
    list_parser.set_defaults(func=list_tarefas)

    # Subparser para marcar uma tarefa como concluída
    complete_parser = subparsers.add_parser("complete", help="Marcar uma tarefa como concluída")
    complete_parser.add_argument("nome", type=str, help="Nome da tarefa")
    complete_parser.set_defaults(func=marcar_tarefa_completa)

    args = parser.parse_args()

    try:
        if args.func:
            args.func(args)
    except Exception as e:
        print(f"Erro: {e}")

def add_tarefa(args):
    manager = TarefaManager()
    tarefa = Tarefa(args.nome)
    manager.adicionar_tarefa(tarefa)
    print(f"Tarefa '{args.nome}' adicionada com sucesso.")

def list_tarefas(args):
    manager = TarefaManager()
    manager.listar_tarefas()

def marcar_tarefa_completa(args):
    manager = TarefaManager()
    manager.marcar_tarefa_completa(args.nome)

if __name__ == "__main__":
    main()