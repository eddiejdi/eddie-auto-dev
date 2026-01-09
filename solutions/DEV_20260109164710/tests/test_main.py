import pytest
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

# Casos de teste para a função get_weather_forecast
def test_get_weather_forecast_valid_city():
    forecast = get_weather_forecast("São Paulo")
    assert "Previsão para São Paulo:" in forecast, "A previsão não contém o título correto."
    assert "Descrição" in forecast, "A previsão não contém a descrição do tempo."
    assert "Temperatura" in forecast, "A previsão não contém a temperatura."
    assert "Humidade" in forecast, "A previsão não contém a humidade."

def test_get_weather_forecast_invalid_city():
    forecast = get_weather_forecast("InvalidCity")
    assert forecast is None, "Deveria retornar None para uma cidade inválida."

def test_get_weather_forecast_exception_handling():
    with pytest.raises(Exception) as e:
        get_weather_forecast("")
    assert str(e.value) == "Erro ao obter previsão do tempo. Código de status: 404", "Deveria lançar um erro para uma cidade inválida."

def test_get_weather_forecast_division_by_zero():
    forecast = get_weather_forecast("InvalidCity")
    with pytest.raises(Exception) as e:
        forecast.split()
    assert str(e.value) == "Erro ao obter previsão do tempo. Código de status: 404", "Deveria lançar um erro para uma cidade inválida."