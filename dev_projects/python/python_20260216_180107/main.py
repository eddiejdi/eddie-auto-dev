class Tarefa:
    def __init__(self, nome):
        self.nome = nome

    def __str__(self):
        return f"Tarefa: {self.nome}"

def main():
    try:
        tarefa1 = Tarefa("Tarefa 1")
        print(tarefa1)
        
        # Adicione mais funcionalidades conforme necessário
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    main()