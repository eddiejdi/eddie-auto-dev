def verificar_mensagem_recebida(recebido: bool) -> str:
    """
    Verifica se a mensagem foi recebida com sucesso por Fernanda Baldi.

    Args:
        recebido (bool): Indica o status da mensagem.

    Returns:
        str: Uma string de confirmação.
    """
    if recebido:
        return 'Mensagem recebida com sucesso.'
    else:
        return 'Mensagem não foi recebida.'

# Casos de teste
print(verificar_mensagem_recebida(True))  # Output: Mensagem recebida com sucesso.
print(verificar_mensagem_recebida(False)) # Output: Mensagem não foi recebida.