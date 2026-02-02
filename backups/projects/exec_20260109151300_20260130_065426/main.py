def verificar_mensagem(mensagem):
    """
    Verifica se a Fernanda Baldi recebeu uma mensagem.

    Args:
    mensagem (str): A mensagem recebida.

    Returns:
    bool: True se a mensagem foi recebida, False caso contrário.
    """
    # Critério para verificar se a mensagem foi recebida
    if "Fernanda" in mensagem and "recebeu" in mensagem:
        return True
    else:
        return False


# Casos de teste
print(verificar_mensagem("Fernanda, você recebeu a mensagem?"))  # Deve retornar True
print(verificar_mensagem("Olá, tudo bem?"))  # Deve retornar False
