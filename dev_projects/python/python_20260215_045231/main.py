class Tarefa:
    def __init__(self, nome):
        self.nome = nome
        self.status = "pendente"

    def marcar_como_concluida(self):
        self.status = "concluída"

def main():
    tarefa1 = Tarefa("Tarefa 1")
    print(f"Tarefa: {tarefa1.nome}, Status: {tarefa1.status}")

    try:
        tarefa1.marcar_como_concluida()
        print(f"Tarefa: {tarefa1.nome}, Status: {tarefa1.status}")
    except Exception as e:
        print(f"Erro ao marcar como concluída: {e}")

if __name__ == "__main__":
    main()