#!/usr/bin/env python
"""
Obter Cotação do Dólar
Auto-desenvolvido em: 2026-01-09T17:29:54.439105
ID: DEV_20260109172705

Desenvolver uma função em Python para obter a cotação atual do dólar em relação ao real brasileiro. A função deve utilizar uma API confiável para buscar os dados e retornar o valor formatado.
"""

import requests

def obter_cotacao_dolar():
    try:
        # URL da API de cotação do dólar
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        
        # Fazer a requisição à API
        response = requests.get(url)
        
        # Verificar se a requisição foi bem-sucedida
        if response.status_code == 200:
            data = response.json()
            
            # Obter a cotação do dólar em relação ao real brasileiro
            cotacao_dolar = data['rates']['BRL']
            
            # Formatar o valor para duas casas decimais
            cotacao_dolar_formatada = f"{cotacao_dolar:.2f}"
            
            return cotacao_dolar_formatada
        else:
            raise Exception(f"Erro ao obter a cotação do dólar: {response.status_code}")
    except requests.RequestException as e:
        raise Exception(f"Erro na requisição à API: {e}")

if __name__ == "__main__":
    cotacao = obter_cotacao_dolar()
    print(f"A cotação atual do dólar é R${cotacao}")
