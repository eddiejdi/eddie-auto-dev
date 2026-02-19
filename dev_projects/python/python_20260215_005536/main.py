class Tarefa:
    def __init__(self, nome):
        self.nome = nome
        self.status = "pendente"

    def marcar_completa(self):
        self.status = "concluída"

    def __str__(self):
        return f"Tarefa: {self.nome}, Status: {self.status}"

def main():
    tarefa1 = Tarefa("Tarefa 1")
    print(tarefa1)

    try:
        tarefa1.marcar_completa()
        print(tarefa1)
    except Exception as e:
        print(f"Erro ao marcar como concluída: {e}")

if __name__ == "__main__":
    main()