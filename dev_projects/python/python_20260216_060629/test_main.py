import pytest
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

# Teste para a função render_template
def test_render_template():
    # Caso de sucesso com valores válidos
    result = app.test_client().get('/')
    assert result.status_code == 200
    assert 'Home' in result.data.decode()

    # Caso de erro (divisão por zero)
    with pytest.raises(ValueError):
        app.test_client().get('/divide/0')

    # Caso de erro (valores inválidos)
    with pytest.raises(ValueError):
        app.test_client().get('/divide/a')

    # Edge case (valores limite, strings vazias, None, etc)
    assert app.test_client().get('/divide/10').status_code == 200
    assert app.test_client().get('/divide/-10').status_code == 200
    assert app.test_client().get('/divide/0.5').status_code == 200
    assert app.test_client().get('/divide/-0.5').status_code == 200