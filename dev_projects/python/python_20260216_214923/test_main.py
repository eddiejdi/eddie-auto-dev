import pytest
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Conexão com o banco de dados SQLite
conn = sqlite3.connect('scrum.db')
c = conn.cursor()

# Criando a tabela se ela não existir
c.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT)''')

@pytest.fixture(scope='module')
def app():
    return app

@pytest.fixture(scope='module')
def client(app):
    return app.test_client()

def test_get_tasks(client):
    response = client.get('/tasks')
    assert response.status_code == 200
    data = response.json
    assert len(data) > 0
    for task in data:
        assert 'id' in task and 'title' in task and 'description' in task

def test_create_task(client):
    response = client.post('/tasks', json={'title': 'Test Task', 'description': 'This is a test task'})
    assert response.status_code == 201
    data = response.json
    assert 'id' in data and 'title' in data and 'description' in data

def test_create_task_with_invalid_data(client):
    response = client.post('/tasks', json={'title': '', 'description': ''})
    assert response.status_code == 400
    data = response.json
    assert 'error' in data and 'Title and description are required' in data['error']

def test_update_task(client, app):
    with app.app_context():
        c.execute('INSERT INTO tasks (title, description) VALUES (?, ?)', ('Test Task', 'This is a test task'))
        conn.commit()
        response = client.put('/tasks/1', json={'title': 'Updated Test Task', 'description': 'This is an updated test task'})
        assert response.status_code == 200
        data = response.json
        assert 'id' in data and 'title' in data and 'description' in data

def test_update_task_with_invalid_data(client):
    with app.app_context():
        c.execute('INSERT INTO tasks (title, description) VALUES (?, ?)', ('Test Task', 'This is a test task'))
        conn.commit()
        response = client.put('/tasks/1', json={'title': '', 'description': ''})
        assert response.status_code == 400
        data = response.json
        assert 'error' in data and 'Title and description are required' in data

def test_delete_task(client, app):
    with app.app_context():
        c.execute('INSERT INTO tasks (title, description) VALUES (?, ?)', ('Test Task', 'This is a test task'))
        conn.commit()
        response = client.delete('/tasks/1')
        assert response.status_code == 204