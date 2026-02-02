import pytest
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
            cotacao_dolar = data["rates"]["BRL"]

            # Formatar o valor para duas casas decimais
            cotacao_dolar_formatada = f"{cotacao_dolar:.2f}"

            return cotacao_dolar_formatada
        else:
            raise Exception(f"Erro ao obter a cotação do dólar: {response.status_code}")
    except requests.RequestException as e:
        raise Exception(f"Erro na requisição à API: {e}")


# Casos de teste para a função obter_cotacao_dolar()


def test_obter_cotacao_dolar_sucesso():
    # Simulando uma resposta bem-sucedida da API
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_data = {"rates": {"BRL": 5.36}}
    mock_response.json = lambda: mock_data

    # Fazendo a requisição à API usando a função mockada
    cotacao = obter_cotacao_dolar()

    # Verificando se o resultado é o esperado
    assert cotacao == "5.36"


def test_obter_cotacao_dolar_erro():
    # Simulando uma resposta de erro da API
    mock_response = requests.Response()
    mock_response.status_code = 404

    # Fazendo a requisição à API usando a função mockada
    with pytest.raises(Exception) as e:
        obter_cotacao_dolar()

    # Verificando se o erro é o esperado
    assert str(e.value) == "Erro ao obter a cotação do dólar: 404"


def test_obter_cotacao_dolar_divisao_presa():
    # Simulando uma resposta bem-sucedida da API
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_data = {"rates": {"BRL": 5.36}}
    mock_response.json = lambda: mock_data

    # Fazendo a requisição à API usando a função mockada
    cotacao = obter_cotacao_dolar()

    # Verificando se o resultado é o esperado após divisão por zero
    assert cotacao == "5.36"
