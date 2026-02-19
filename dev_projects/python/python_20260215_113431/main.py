import os

class Tarefa1:
    def __init__(self):
        self.task_name = "Tarefa 1"
        self.description = "Implemente todas as funcionalidades listadas nos requisitos"

    def execute(self):
        try:
            # Implementação da tarefa 1 aqui
            print(f"Executando {self.task_name}")
            # Adicione suas implementações aqui
            pass

        except Exception as e:
            print(f"Erro ao executar {self.task_name}: {e}")

if __name__ == "__main__":
    tarefa1 = Tarefa1()
    tarefa1.execute()