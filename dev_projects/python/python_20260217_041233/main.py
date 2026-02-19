# Tarefa 1: Implementação de uma classe com funções

class Calculadora:
    def __init__(self):
        self.resultado = 0

    def adicionar(self, num):
        try:
            self.resultado += num
            return f"Adição realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"

    def subtrair(self, num):
        try:
            self.resultado -= num
            return f"Subtração realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"

    def multiplicar(self, num):
        try:
            self.resultado *= num
            return f"Multiplicação realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"

    def dividir(self, num):
        try:
            if num == 0:
                raise ValueError("Divisão por zero não é permitida")
            self.resultado /= num
            return f"Divisão realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"
        except ValueError as e:
            return f"Erro: {e}"

# Função principal para execução do programa

def main():
    calculadora = Calculadora()

    while True:
        print("\nOpções:")
        print("1. Adicionar")
        print("2. Subtrair")
        print("3. Multiplicar")
        print("4. Dividir")
        print("5. Sair")

        opcao = input("Digite a opção desejada: ")

        if opcao == '1':
            num = float(input("Digite o número para adicionar: "))
            print(calculadora.adicionar(num))
        elif opcao == '2':
            num = float(input("Digite o número para subtrair: "))
            print(calculadora.subtrair(num))
        elif opcao == '3':
            num = float(input("Digite o número para multiplicar: "))
            print(calculadora.multiplicar(num))
        elif opcao == '4':
            num = float(input("Digite o número para dividir: "))
            print(calculadora.dividir(num))
        elif opcao == '5':
            print("Saindo do programa...")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()