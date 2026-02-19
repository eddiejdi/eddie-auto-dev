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
            return f"Erro: {str(e)}"

    def listar_tarefas(self):
        try:
            if self.tarefas:
                return "\n".join(self.tarefas)
            else:
                return "Nenhuma tarefa adicionada."
        except Exception as e:
            return f"Erro: {str(e)}"

    def remover_tarefa(self, index):
        try:
            if 0 <= index < len(self.tarefas):
                removed_task = self.tarefas.pop(index)
                return f"Tarefa '{removed_task}' removida com sucesso."
            else:
                raise IndexError("Índice inválido.")
        except Exception as e:
            return f"Erro: {str(e)}"

    def __repr__(self):
        return f"Tarefa1({self.tarefas})"


if __name__ == "__main__":
    tarefa1 = Tarefa1()
    print(tarefa1.adicionar_tarefa("Entregar projeto"))
    print(tarefa1.listar_tarefas())
    print(tarefa1.remover_tarefa(0))
    print(tarefa1)