import pytest

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
@pytest.mark.parametrize("mensagem", ["Hello", "", None])
def test_verificar_recebimento(mensagem):
    assert verificar_recebimento(mensagem), f"Verificação falhou para {mensagem}"