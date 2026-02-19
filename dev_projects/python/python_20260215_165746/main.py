import json

class Tarefa:
    def __init__(self, id, nome, descricao):
        self.id = id
        self.nome = nome
        self.descricao = descricao

    def to_json(self):
        return json.dumps({
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao
        })

class TarefaService:
    def __init__(self, tarefas=None):
        if tarefas is None:
            self.tarefas = []
        else:
            self.tarefas = tarefas

    def adicionar_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def listar_tarefas(self):
        return [tarefa.to_json() for tarefa in self.tarefas]

    def remover_tarefa(self, id):
        self.tarefas = [tarefa for tarefa in self.tarefas if tarefa.id != id]

def main():
    # Criar um serviço de tarefas
    service = TarefaService()

    # Adicionar algumas tarefas
    service.adicionar_tarefa(Tarefa(1, "Tarefa 1", "Descrição da Tarefa 1"))
    service.adicionar_tarefa(Tarefa(2, "Tarefa 2", "Descrição da Tarefa 2"))

    # Listar todas as tarefas
    print("Tarefas:")
    for task in service.listar_tarefas():
        print(task)

    # Remover uma tarefa
    service.remover_tarefa(1)
    print("\nTarefas após remover a Tarefa 1:")
    for task in service.listar_tarefas():
        print(task)

if __name__ == "__main__":
    main()