import pytest

from app import tasks, get_tasks, create_task, update_task, delete_task

def test_get_tasks():
    assert get_tasks().status_code == 200
    assert isinstance(get_tasks(), list)

def test_create_task_valid_data():
    data = {'title': 'Test Task'}
    response = create_task(data)
    assert response.status_code == 201
    assert 'id' in response.json()

def test_create_task_invalid_data():
    data = {}
    response = create_task(data)
    assert response.status_code == 400

def test_update_task_valid_data():
    task_id = tasks[0]['id']
    new_data = {'title': 'Updated Task'}
    response = update_task(task_id, new_data)
    assert response.status_code == 200
    assert 'title' in response.json()

def test_update_task_invalid_data():
    task_id = tasks[0]['id']
    data = {}
    response = update_task(task_id, data)
    assert response.status_code == 400

def test_delete_task_valid_data():
    task_id = tasks[0]['id']
    response = delete_task(task_id)
    assert response.status_code == 200
    assert 'message' in response.json()

def test_delete_task_invalid_data():
    task_id = -1
    response = delete_task(task_id)
    assert response.status_code == 404

def test_edge_cases():
    # Teste com string vazia
    data = {'title': ''}
    response = create_task(data)
    assert response.status_code == 400

    # Teste com None
    data = {'title': None}
    response = create_task(data)
    assert response.status_code == 400

    # Teste com float
    data = {'title': 123.45}
    response = create_task(data)
    assert response.status_code == 400

    # Teste com zero
    data = {'title': 0}
    response = create_task(data)
    assert response.status_code == 400