import pytest

def verificar_mensagem(mensagem):
    """
    Verifica se a Fernanda Baldi recebeu uma mensagem específica.

    Args:
        mensagem (str): A mensagem recebida.

    Returns:
        bool: True se a mensagem foi recebida, False caso contrário.
    """
    return mensagem == 'Fernanda Baldi recebeu a mensagem?'

# Casos de teste
def test_verificar_mensagem_sucesso():
    assert verificar_mensagem('Fernanda Baldi recebeu a mensagem?') == True

def test_verificar_mensagem_erro():
    assert verificar_mensagem('Outra mensagem qualquer') == False

def test_verificar_mensagem_divisao_zero():
    with pytest.raises(ZeroDivisionError):
        verificar_mensagem('Fernanda Baldi recebeu a mensagem?')

def test_verificar_mensagem_valores_invalidos():
    assert verificar_mensagem(None) == False
    assert verificar_mensagem([]) == False

def test_verificar_mensagem_string_vazia():
    assert verificar_mensagem("") == False

def test_verificar_mensagem_edge_cases():
    assert verificar_mensagem('Fernanda Baldi recebeu a mensagem?') == True
    assert verificar_mensagem('Fernanda Baldi recebeu a mensagem?') == True