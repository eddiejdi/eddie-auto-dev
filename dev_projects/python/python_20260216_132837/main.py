# Importando os módulos necessários
import argparse

class Tarefa1:
    def __init__(self):
        # Inicialização da classe
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        # Adiciona uma nova tarefa à lista
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        # Lista todas as tarefas existentes
        return self.tarefas

    def remover_tarefa(self, index):
        # Remove uma tarefa pelo índice
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

if __name__ == "__main__":
    # Criando um parser para receber argumentos do CLI
    parser = argparse.ArgumentParser(description="Tarefa 1")
    parser.add_argument("--adicionar", type=str, help="Adicionar uma nova tarefa")
    parser.add_argument("--listar", action="store_true", help="Listar todas as tarefas")
    parser.add_argument("--remover", type=int, help="Remover uma tarefa pelo índice")

    # Processando os argumentos
    args = parser.parse_args()

    if args.adicionar:
        tarefa1 = Tarefa1()
        tarefa1.adicionar_tarefa(args.adicionar)
        print("Tarefa adicionada:", tarefa1.listar_tarefas())

    elif args.listar:
        tarefa1 = Tarefa1()
        print("Tarefas existentes:", tarefa1.listar_tarefas())

    elif args.remover:
        try:
            tarefa1 = Tarefa1()
            tarefa1.remover_tarefa(args.remover)
            print("Tarefa removida:", tarefa1.listar_tarefas())
        except IndexError as e:
            print(e)

    else:
        parser.print_help()