import pytest


def obter_previsao_tempo_jundiai():
    api_key = "your_api_key_here"
    previsao_tempo = PrevisaoTempo(api_key)

    try:
        cidade = input("Digite a cidade para obter a previsão do tempo: ")
        previsao = previsao_tempo.obter_previsao_tempo(cidade)

        return previsao
    except Exception as e:
        print(e)


class TestPrevisaoTempoJundiai:
    def test_obter_previsao_tempo_jundiai_success(self):
        previsao = obter_previsao_tempo_jundiai()
        assert isinstance(previsao, dict)
        # Add assertions to check specific keys and values in the dictionary

    def test_obter_previsao_tempo_jundiai_error(self):
        with pytest.raises(Exception) as e:
            obter_previsao_tempo_jundiai()
        assert "Erro ao obter previsão do tempo" in str(e)

    # Add more test cases as needed
