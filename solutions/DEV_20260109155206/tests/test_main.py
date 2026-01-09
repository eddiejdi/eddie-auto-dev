import pytest

def verificar_mensagem(mensagem):
    """
    Verifica se a Fernanda Baldi recebeu uma mensagem específica.

    Args:
    mensagem (str): A mensagem recebida.

    Returns:
    bool: True se a mensagem for 'Fernanda Baldi recebeu a mensagem?', False caso contrário.
    """
    return mensagem == 'Fernanda Baldi recebeu a mensagem?'

# Casos de teste
def test_verificar_mensagem_sucesso():
    assert verificar_mensagem('Fernanda Baldi recebeu a mensagem?') == True

def test_verificar_mensagem_erro():
    assert verificar_mensagem('Outra mensagem qualquer') == False

def test_verificar_mensagem_edge_case():
    assert verificar_mensagem(None) == False