#!/usr/bin/env python
"""
Verificação de Mensagem Recebida
Auto-desenvolvido em: 2026-01-09T15:55:50.604538
ID: DEV_20260109155229

Desenvolver uma função em Python que verifica se a Fernanda Baldi recebeu uma mensagem específica. A função deve receber como parâmetro a mensagem e retornar um booleano indicando se a mensagem foi recebida.
"""

def verificar_mensagem(mensagem):
    """
    Verifica se a Fernanda Baldi recebeu uma mensagem específica.

    Args:
        mensagem (str): A mensagem recebida.

    Returns:
        bool: True se a mensagem foi recebida, False caso contrário.
    """
    return 'Fernanda Baldi' in mensagem

# Casos de teste
print(verificar_mensagem('Olá Fernanda Baldi!'))  # True
print(verificar_mensagem('Hello, world!'))  # False
