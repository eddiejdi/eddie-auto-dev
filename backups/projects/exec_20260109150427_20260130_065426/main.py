def verificar_mensagem(mensagem):
    """
    Verifica se a Fernanda Baldi recebeu uma mensagem específica.

    Args:
        mensagem (str): A mensagem recebida.

    Returns:
        bool: True se a mensagem foi recebida, False caso contrário.
    """
    return mensagem == "Fernanda Baldi recebeu a mensagem?"


# Casos de teste
print(verificar_mensagem("Fernanda Baldi recebeu a mensagem?"))  # Deve retornar True
print(verificar_mensagem("Outra mensagem qualquer"))  # Deve retornar False
