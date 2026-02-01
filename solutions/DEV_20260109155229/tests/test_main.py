def verificar_mensagem(mensagem):
    """
    Verifica se a Fernanda Baldi recebeu uma mensagem específica.

    Args:
        mensagem (str): A mensagem recebida.

    Returns:
        bool: True se a mensagem foi recebida, False caso contrário.
    """
    return "Fernanda Baldi" in mensagem


# Casos de teste
def test_verificar_mensagem_sucesso():
    assert verificar_mensagem("Olá Fernanda Baldi!") == True


def test_verificar_mensagem_erro():
    assert verificar_mensagem("Hello, world!") == False


def test_verificar_mensagem_edge_case():
    assert verificar_mensagem("Fernanda Baldi") == True
