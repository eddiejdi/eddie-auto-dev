class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        try:
            if isinstance(tarefa, str):
                self.tarefas.append(tarefa)
                return f"Tarefa '{tarefa}' adicionada com sucesso."
            else:
                raise ValueError("A tarefa deve ser uma string.")
        except Exception as e:
            return f"Erro: {e}"

    def listar_tarefas(self):
        try:
            if self.tarefas:
                return "\n".join(self.tarefas)
            else:
                return "Não há tarefas adicionadas."
        except Exception as e:
            return f"Erro: {e}"

    def remover_tarefa(self, index):
        try:
            if 0 <= index < len(self.tarefas):
                removed_task = self.tarefas.pop(index)
                return f"Tarefa '{removed_task}' removida com sucesso."
            else:
                raise IndexError("Índice inválido.")
        except Exception as e:
            return f"Erro: {e}"

    def buscar_tarefa(self, tarefa):
        try:
            if isinstance(tarefa, str):
                for index, task in enumerate(self.tarefas):
                    if task == tarefa:
                        return f"Tarefa '{tarefa}' encontrada na posição {index}."
                return "Tarefa não encontrada."
            else:
                raise ValueError("A tarefa deve ser uma string.")
        except Exception as e:
            return f"Erro: {e}"

if __name__ == "__main__":
    tarefa1 = Tarefa1()

    print(tarefa1.adicionar_tarefa("Fazer compras"))
    print(tarefa1.adicionar_tarefa("Levar dinheiro para a loja"))

    print(tarefa1.listar_tarefas())

    print(tarefa1.remover_tarefa(0))

    print(tarefa1.buscar_tarefa("Fazer compras"))