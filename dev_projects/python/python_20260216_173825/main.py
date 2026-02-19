def fatorial(n):
    """Calcula o fatorial de um número."""
    if n < 0:
        raise ValueError("O fatorial não é definido para números negativos.")
    elif n == 0 or n == 1:
        return 1
    else:
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

def main():
    """Função principal que chama a função_fatorial."""
    try:
        num = int(input("Digite um número para calcular o fatorial: "))
        print(f"O fatorial de {num} é {fatorial(num)}")
    except ValueError as e:
        print(e)

if __name__ == "__main__":
    main()