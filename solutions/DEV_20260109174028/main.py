#!/usr/bin/env python
"""
API para obter cotação do dólar
Auto-desenvolvido em: 2026-01-09T17:42:53.253487
ID: DEV_20260109174028

Desenvolver uma API em Python que retorna a cotação atual do dólar em relação ao real brasileiro.
"""

import requests

class CotacaoDolar:
    def __init__(self):
        self.url = "https://api.exchangerate-api.com/v4/latest/BRL"

    def obter_cotacao(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()  # Verifica se a requisição foi bem-sucedida
            cotacao_data = response.json()
            return cotacao_data['rates']['USD']
        except requests.RequestException as e:
            print(f"Erro ao obter cotação do dólar: {e}")
            return None

if __name__ == "__main__":
    cotacao_dolar = CotacaoDolar()
    cotacao = cotacao_dolar.obter_cotacao()

    if cotacao is not None:
        print(f"A cotação atual do dólar é R${cotacao:.2f}")
