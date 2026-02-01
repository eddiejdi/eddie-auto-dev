#!/usr/bin/env python
"""
Verificação de Mensagem Recebida
Auto-desenvolvido em: 2026-01-09T15:34:16.974904
ID: DEV_20260109153108

Desenvolver uma função em Python para verificar se a mensagem foi recebida com sucesso por Fernanda Baldi. A função deve receber um parâmetro booleano indicando o status da mensagem e retornar uma string de confirmação.
"""


def verificar_mensagem_recebida(recebido: bool) -> str:
    """
    Verifica se a mensagem foi recebida com sucesso por Fernanda Baldi.

    Args:
        recebido (bool): Indica o status da mensagem.

    Returns:
        str: Uma string de confirmação.
    """
    if recebido:
        return "Mensagem recebida com sucesso."
    else:
        return "Mensagem não foi recebida."


# Casos de teste
print(verificar_mensagem_recebida(True))  # Output: Mensagem recebida com sucesso.
print(verificar_mensagem_recebida(False))  # Output: Mensagem não foi recebida.
