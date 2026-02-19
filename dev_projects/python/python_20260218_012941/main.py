def fatorial(n):
    """
    Calcula o fatorial de um número n.
    
    Args:
    n (int): O número para calcular o fatorial.
    
    Returns:
    int: O fatorial de n.
    """
    if n < 0:
        raise ValueError("O fatorial não é definido para números negativos")
    elif n == 0 or n == 1:
        return 1
    else:
        return n * fatorial(n - 1)

def main():
    try:
        num = int(input("Digite um número para calcular o fatorial: "))
        result = fatorial(num)
        print(f"O fatorial de {num} é {result}")
    except ValueError as e:
        print(e)

if __name__ == "__main__":
    main()