#!/usr/bin/env python
"""
Previsão de Tempo para Jundiaí
Auto-desenvolvido em: 2026-01-09T19:22:47.562823
ID: DEV_20260109192009

Desenvolver uma função em Python que retorna a previsão do tempo para a cidade de Jundiaí, utilizando uma API de previsão meteorológica.
"""

import requests


class PrevisaoTempo:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"

    def obter_previsao_tempo(self, cidade):
        params = {
            "q": cidade,
            "appid": self.api_key,
            "units": "metric",  # Celsius
        }
        response = requests.get(self.base_url, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Erro ao obter previsão do tempo: {response.status_code}")


def main():
    api_key = "your_api_key_here"
    previsao_tempo = PrevisaoTempo(api_key)

    try:
        cidade = input("Digite a cidade para obter a previsão do tempo: ")
        previsao = previsao_tempo.obter_previsao_tempo(cidade)

        print(f"Previsão do Tempo para {cidade}:")
        print(previsao)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
