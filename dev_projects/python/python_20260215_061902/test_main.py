import pytest
from flask import request
from sqlalchemy.exc import IntegrityError
from app import app, Task

@pytest.fixture
def client():
    return app.test_client()

def test_get_tasks(client):
    response = client.get('/tasks')
    assert response.status_code == 200
    assert isinstance(response.json, list)

def test_create_task_valid(client):
    data = {'title': 'Test task', 'description': 'This is a test task'}
    response = client.post('/tasks', json=data)
    assert response.status_code == 201
    assert 'id' in response.json

def test_create_task_invalid_title(client):
    data = {'title': '', 'description': 'This is a test task'}
    response = client.post('/tasks', json=data)
    assert response.status_code == 400
    assert 'title' in response.json

def test_create_task_invalid_description(client):
    data = {'title': 'Test task', 'description': ''}
    response = client.post('/tasks', json=data)
    assert response.status_code == 400
    assert 'description' in response.json

def test_update_task_valid(client, task):
    new_data = {'title': 'Updated task', 'description': 'This is an updated task'}
    response = client.put(f'/tasks/{task.id}', json=new_data)
    assert response.status_code == 200
    assert 'id' in response.json

def test_update_task_invalid_title(client, task):
    new_data = {'title': '', 'description': 'This is an updated task'}
    response = client.put(f'/tasks/{task.id}', json=new_data)
    assert response.status_code == 400
    assert 'title' in response.json

def test_update_task_invalid_description(client, task):
    new_data = {'title': 'Updated task', 'description': ''}
    response = client.put(f'/tasks/{task.id}', json=new_data)
    assert response.status_code == 400
    assert 'description' in response.json

def test_delete_task_valid(client, task):
    response = client.delete(f'/tasks/{task.id}')
    assert response.status_code == 204

def test_delete_task_invalid_id(client):
    response = client.delete('/tasks/999')
    assert response.status_code == 404