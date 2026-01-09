#!/usr/bin/env python
"""
Previsão de Tempo para Jundiaí
Auto-desenvolvido em: 2026-01-09T18:11:40.263667
ID: DEV_20260109180714

Desenvolver uma função em Python que retorna a previsão do tempo para a cidade de Jundiaí, utilizando uma API externa como OpenWeatherMap.
"""

import requests

def get_weather_forecast_jundiai(api_key):
    url = f"http://api.openweathermap.org/data/2.5/weather?q=Jundiaí&appid={api_key}&units=metric"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        data = response.json()
        
        if 'main' in data and 'description' in data['weather'][0]:
            temperature = data['main']['temp']
            description = data['weather'][0]['description']
            return f"Tempo: {temperature}°C, Descrição: {description}"
        else:
            return "Dados insuficientes na resposta da API."
    except requests.RequestException as e:
        return f"Erro ao fazer a requisição: {e}"

if __name__ == "__main__":
    api_key = "your_api_key_here"
    forecast = get_weather_forecast_jundiai(api_key)
    print(forecast)
