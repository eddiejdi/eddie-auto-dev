#!/usr/bin/env python
"""
Previsão do Tempo para Amanhã
Auto-desenvolvido em: 2026-01-09T16:50:13.187930
ID: DEV_20260109164710

Desenvolver uma função em Python que retorna a previsão do tempo para amanhã usando uma API de previsão do tempo confiável.
"""

import requests

def get_weather_forecast(city):
    # URL da API OpenWeatherMap para previsão do tempo
    api_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid=YOUR_API_KEY"
    
    try:
        # Faz a requisição à API
        response = requests.get(api_url)
        
        # Verifica se a resposta foi bem-sucedida
        if response.status_code == 200:
            data = response.json()
            
            # Extrai os dados relevantes da previsão do tempo
            weather_description = data['weather'][0]['description']
            temperature = data['main']['temp']
            humidity = data['main']['humidity']
            
            # Formata e retorna os dados em um formato legível
            forecast = f"Previsão para {city}:\nDescrição: {weather_description}\nTemperatura: {temperature:.2f}°C\nHumidade: {humidity}%"
            return forecast
        
        else:
            raise Exception(f"Erro ao obter previsão do tempo. Código de status: {response.status_code}")
    
    except requests.exceptions.RequestException as e:
        # Trata exceções relacionadas à requisição
        print(f"Erro na requisição: {e}")
        return None

if __name__ == "__main__":
    city = input("Digite a cidade para obter a previsão do tempo: ")
    forecast = get_weather_forecast(city)
    
    if forecast:
        print(forecast)
    else:
        print("Falha ao obter a previsão do tempo.")
