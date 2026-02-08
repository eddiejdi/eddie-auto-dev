def verificar_recebimento(mensagem):
    """
    Verifica se a mensagem foi recebida com sucesso.

    Args:
    mensagem (str): A mensagem a ser verificada.

    Returns:
    bool: True se a mensagem foi recebida, False caso contrário.
    """
    if mensagem is not None and mensagem != "":
        return True
    else:
        return False

# Casos de teste
print(verificar_recebimento("Hello"))  # Output: True
print(verificar_recebimento(""))      # Output: False