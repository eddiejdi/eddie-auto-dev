import requests


class CotacaoDolar:
    def __init__(self):
        self.url = "https://api.exchangerate-api.com/v4/latest/BRL"

    def obter_cotacao(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()  # Verifica se a requisição foi bem-sucedida
            cotacao_data = response.json()
            return cotacao_data["rates"]["USD"]
        except requests.RequestException as e:
            print(f"Erro ao obter cotação do dólar: {e}")
            return None


# Testes para obter_cotacao
def test_obter_cotacao_sucesso():
    cotacao_dolar = CotacaoDolar()
    cotacao = cotacao_dolar.obter_cotacao()
    assert cotacao is not None, "Deveria retornar uma cotação válida"
    assert isinstance(cotacao, float), "A cotação deve ser um número"


def test_obter_cotacao_erro():
    cotacao_dolar = CotacaoDolar()
    cotacao = cotacao_dolar.obter_cotacao()
    assert cotacao is None, "Deveria retornar None em caso de erro"
