import pytest
from flask import Flask, jsonify, request
import uuid

app = Flask(__name__)

# Lista de tarefas em memória
tasks = []

@app.route('/tasks', methods=['POST'])
def create_task():
    try:
        data = request.get_json()
        task_id = str(uuid.uuid4())
        task = {
            'id': task_id,
            'title': data['title'],
            'description': data.get('description', ''),
            'status': 'pending'
        }
        tasks.append(task)
        return jsonify({'message': 'Task created successfully', 'task': task}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        data = request.get_json()
        for task in tasks:
            if task['id'] == task_id:
                task.update(data)
                return jsonify({'message': 'Task updated successfully', 'task': task}), 200
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        global tasks
        tasks = [task for task in tasks if task['id'] != task_id]
        return jsonify({'message': 'Task deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/tasks', methods=['GET'])
def get_tasks():
    try:
        return jsonify({'tasks': tasks}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

# Testes unitários

def test_create_task_success():
    client = app.test_client()
    response = client.post('/tasks', json={'title': 'Test Task'})
    assert response.status_code == 201
    task = response.json['task']
    assert task['id'] != ''
    assert task['title'] == 'Test Task'
    assert task['description'] == ''
    assert task['status'] == 'pending'

def test_create_task_invalid_title():
    client = app.test_client()
    response = client.post('/tasks', json={'title': ''})
    assert response.status_code == 400
    assert response.json['error'].startswith('Invalid title')

def test_create_task_invalid_description():
    client = app.test_client()
    response = client.post('/tasks', json={'description': 'Test Description'})
    assert response.status_code == 201
    task = response.json['task']
    assert task['id'] != ''
    assert task['title'] == 'Test Task'
    assert task['description'] == 'Test Description'
    assert task['status'] == 'pending'

def test_create_task_invalid_data():
    client = app.test_client()
    response = client.post('/tasks', json={'invalid': 'data'})
    assert response.status_code == 400
    assert response.json['error'].startswith('Invalid data')

def test_update_task_success():
    client = app.test_client()
    create_response = client.post('/tasks', json={'title': 'Test Task'})
    task_id = create_response.json['task']['id']
    update_data = {'description': 'Updated Description'}
    response = client.put(f'/tasks/{task_id}', json=update_data)
    assert response.status_code == 200
    task = response.json['task']
    assert task['id'] == task_id
    assert task['title'] == 'Test Task'
    assert task['description'] == 'Updated Description'
    assert task['status'] == 'pending'

def test_update_task_invalid_data():
    client = app.test_client()
    create_response = client.post('/tasks', json={'title': 'Test Task'})
    task_id = create_response.json['task']['id']
    update_data = {'invalid': 'data'}
    response = client.put(f'/tasks/{task_id}', json=update_data)
    assert response.status_code == 400
    assert response.json['error'].startswith('Invalid data')

def test_delete_task_success():
    client = app.test_client()
    create_response = client.post('/tasks', json={'title': 'Test Task'})
    task_id = create_response.json['task']['id']
    response = client.delete(f'/tasks/{task_id}')
    assert response.status_code == 200
    assert not any(task['id'] == task_id for task in tasks)

def test_delete_task_invalid_id():
    client = app.test_client()
    response = client.delete('/tasks/invalid-id')
    assert response.status_code == 404

def test_get_tasks_success():
    client = app.test_client()
    create_response = client.post('/tasks', json={'title': 'Test Task'})
    task_id = create_response.json['task']['id']
    get_response = client.get('/tasks')
    assert get_response.status_code == 200
    tasks = get_response.json['tasks']
    assert any(task['id'] == task_id for task in tasks)

def test_get_tasks_empty():
    client = app.test_client()
    get_response = client.get('/tasks')
    assert get_response.status_code == 200
    assert not tasks

def test_get_tasks_invalid_data():
    client = app.test_client()
    response = client.get('/tasks', json={'invalid': 'data'})
    assert response.status_code == 400
    assert response.json['error'].startswith('Invalid data')