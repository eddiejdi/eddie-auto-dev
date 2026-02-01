#!/usr/bin/env python
"""
Verificação de Mensagem Recebida
Auto-desenvolvido em: 2026-01-09T15:55:37.380110
ID: DEV_20260109155206

Desenvolver uma função em Python para verificar se a Fernanda Baldi recebeu uma mensagem específica. A função deve receber como parâmetro a mensagem e retornar um booleano indicando se a mensagem foi recebida.
"""


def verificar_mensagem(mensagem):
    """
    Verifica se a Fernanda Baldi recebeu uma mensagem específica.

    Args:
    mensagem (str): A mensagem recebida.

    Returns:
    bool: True se a mensagem for 'Fernanda Baldi recebeu a mensagem?', False caso contrário.
    """
    return mensagem == "Fernanda Baldi recebeu a mensagem?"


# Casos de teste
print(verificar_mensagem("Fernanda Baldi recebeu a mensagem?"))  # Deve retornar True
print(verificar_mensagem("Outra mensagem qualquer"))  # Deve retornar False
