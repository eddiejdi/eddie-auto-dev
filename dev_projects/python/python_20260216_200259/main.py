from typing import List

class Tarefa:
    def __init__(self, id: int, nome: str):
        self.id = id
        self.nome = nome
        self.status = "pendente"

    def marcar_completa(self):
        self.status = "completa"

def listar_tarefas(tarefas: List[Tarefa]) -> None:
    for tarefa in tarefas:
        print(f"{tarefa.id}: {tarefa.nome} - Status: {tarefa.status}")

def criar_tarefa(id: int, nome: str) -> Tarefa:
    return Tarefa(id, nome)

def main() -> None:
    try:
        tarefas = []
        
        # Criar algumas tarefas
        t1 = criar_tarefa(1, "Tarefa 1")
        t2 = criar_tarefa(2, "Tarefa 2")
        
        # Adicionar às tarefas
        tarefas.append(t1)
        tarefas.append(t2)
        
        # Listar todas as tarefas
        listar_tarefas(tarefas)
        
        # Marcar uma tarefa como completa
        t1.marcar_completa()
        
        # Listar novamente para confirmar a atualização
        listar_tarefas(tarefas)
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()