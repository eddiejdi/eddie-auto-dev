class Tarefa:
    def __init__(self, nome):
        self.nome = nome

    def listar(self):
        return f"Tarefa: {self.nome}"

def main():
    tarefa1 = Tarefa("Tarefa 1")
    print(tarefa1.listar())

if __name__ == "__main__":
    main()