#!/usr/bin/env python3
"""
Arquivo de teste para Eddie Copilot
Abra este arquivo no VS Code e teste as funcionalidades:

1. AUTOCOMPLETE: Posicione o cursor após "def " e aguarde sugestões
2. CHAT: Use Ctrl+Shift+I para abrir o chat
3. STATUS: Clique no Eddie [L] na barra de status

Exemplos para testar autocomplete:
"""
# Exemplos para testes de autocomplete guardados como string para evitar
# erros de sintaxe durante checks automáticos (mantém o conteúdo para
# uso interativo no editor).
EXAMPLES = '''
Teste 1: Função incompleta
def calculate_sum

Teste 2: Lista incompleta
numbers = [1, 2, 3,

Teste 3: Classe incompleta
class Person:
    def __init__

Teste 4: Import incompleto
import

Teste 5: Docstring
def hello_world():
    """
    
    """
    pass

Teste 6: For loop
for i in range

Teste 7: Dict comprehension
data = {

Teste 8: Try/except
try:
    result = 10 / 0
except

Teste 9: With statement
with open("file.txt",

Teste 10: Lambda
square = lambda
'''

def _noop():
    pass
