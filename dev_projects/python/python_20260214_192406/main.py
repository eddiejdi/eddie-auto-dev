# Importações necessárias
import json

class Tarefa:
    def __init__(self, id, descricao, status):
        self.id = id
        self.descricao = descricao
        self.status = status

    def to_json(self):
        return json.dumps({
            "id": self.id,
            "descricao": self.descricao,
            "status": self.status
        })

class TarefaService:
    def __init__(self):
        self.tarefas = []

    def add_tarefa(self, tarefa):
        self.tarefas.append(tarefa)

    def get_tarefas(self):
        return self.tarefas

    def update_tarefa(self, id, descricao=None, status=None):
        for tarefa in self.tarefas:
            if tarefa.id == id:
                if descricao is not None:
                    tarefa.descricao = descricao
                if status is not None:
                    tarefa.status = status
                return True
        return False

    def delete_tarefa(self, id):
        self.tarefas = [tarefa for tarefa in self.tarefas if tarefa.id != id]

def main():
    # Criando um serviço de tarefas
    service = TarefaService()

    # Adicionando algumas tarefas
    tarefa1 = Tarefa(1, "Entregar projeto", "Pendente")
    tarefa2 = Tarefa(2, "Lavar o carro", "Concluído")
    service.add_tarefa(tarefa1)
    service.add_tarefa(tarefa2)

    # Listando todas as tarefas
    print("Tarefas:")
    for tarefa in service.get_tarefas():
        print(tarefa.to_json())

    # Atualizando uma tarefa
    service.update_tarefa(1, descricao="Entregar projeto em tempo limite")

    # Listando novamente as tarefas para verificar a atualização
    print("\nTarefas após atualização:")
    for tarefa in service.get_tarefas():
        print(tarefa.to_json())

    # Deletando uma tarefa
    service.delete_tarefa(2)

    # Listando finalmente todas as tarefas para verificar a exclusão
    print("\nTarefas após exclusão:")
    for tarefa in service.get_tarefas():
        print(tarefa.to_json())

if __name__ == "__main__":
    main()