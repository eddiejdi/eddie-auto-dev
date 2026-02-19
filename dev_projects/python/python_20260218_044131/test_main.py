import pytest
from flask import request, jsonify, make_response
import sqlite3

# Conectar ao banco de dados (criar se não existir)
conn = sqlite3.connect('items.db')
c = conn.cursor()

# Criar tabela se ela não existir
c.execute('''CREATE TABLE IF NOT EXISTS items
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL)''')

conn.commit()

@pytest.fixture
def app():
    # Configura o Flask para rodar em modo de teste
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    # Cria um cliente do Flask para testes
    with app.test_client() as client:
        yield client

def test_add_item_success(client):
    data = {'name': 'Item 1'}
    response = client.post('/items', json=data)
    assert response.status_code == 200
    assert response.json['message'] == f'Item {response.json["id"]} added successfully'

def test_add_item_invalid_request(client):
    response = client.post('/items')
    assert response.status_code == 400

def test_list_items_success(client):
    data = {'name': 'Item 1'}
    client.post('/items', json=data)
    response = client.get('/items')
    assert response.status_code == 200
    items = [{'id': row[0], 'name': row[1]} for row in c.fetchall()]
    assert len(items) == 1

def test_list_items_no_items(client):
    response = client.get('/items')
    assert response.status_code == 200
    assert not response.json

def test_delete_item_success(client):
    data = {'name': 'Item 1'}
    client.post('/items', json=data)
    item_id = c.lastrowid
    response = client.delete(f'/items/{item_id}')
    assert response.status_code == 200
    assert response.json['message'] == f'Item {item_id} deleted successfully'

def test_delete_item_not_found(client):
    response = client.delete('/items/1')
    assert response.status_code == 404

def test_delete_item_invalid_request(client):
    response = client.delete('/items')
    assert response.status_code == 400