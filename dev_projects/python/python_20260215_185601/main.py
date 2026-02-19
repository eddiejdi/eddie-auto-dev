# Importações necessárias
import sys

def functionality_to_sum_two_numbers(a: int, b: int) -> int:
    """
    Soma dois números e retorna o resultado.
    
    Args:
        a (int): O primeiro número.
        b (int): O segundo número.
        
    Returns:
        int: A soma dos dois números.
    """
    try:
        return a + b
    except TypeError as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    """
    Função principal que executa o programa.
    
    Args:
        None
        
    Returns:
        None
    """
    # Exemplo de uso da função
    result = functionality_to_sum_two_numbers(5, 3)
    print(f"The sum of 5 and 3 is: {result}")

if __name__ == "__main__":
    main()