import pytest
from flask import jsonify, request

# Simulação de banco de dados
tasks = []

@pytest.fixture
def app():
    app = Flask(__name__)
    return app

@app.route('/tasks', methods=['GET'])
def get_tasks(app):
    with app.test_request_context():
        response = jsonify(tasks)
        return response

@app.route('/tasks', methods=['POST'])
def create_task(app):
    task = request.get_json()
    tasks.append(task)
    with app.test_request_context():
        response = jsonify(task), 201
        return response

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(app, task_id):
    task = next((t for t in tasks if t['id'] == task_id), None)
    if not task:
        with app.test_request_context():
            response = jsonify({'error': 'Task not found'}), 404
            return response
    task.update(request.get_json())
    with app.test_request_context():
        response = jsonify(task)
        return response

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(app, task_id):
    global tasks
    tasks = [t for t in tasks if t['id'] != task_id]
    with app.test_request_context():
        response = jsonify({'message': 'Task deleted'})
        return response

def test_get_tasks(app):
    # Caso de sucesso com valores válidos
    assert get_tasks(app).status_code == 200
    assert len(get_tasks(app).get_json()) == 0

def test_create_task(app):
    # Caso de sucesso com valores válidos
    task = {'id': 1, 'description': 'Teste'}
    response = create_task(app, task)
    assert response.status_code == 201
    assert response.get_json() == task

def test_update_task(app):
    # Caso de sucesso com valores válidos
    task = {'id': 1, 'description': 'Teste'}
    create_task(app, task)
    updated_task = {'id': 1, 'description': 'Updated Teste'}
    response = update_task(app, 1, updated_task)
    assert response.status_code == 200
    assert response.get_json() == updated_task

def test_delete_task(app):
    # Caso de sucesso com valores válidos
    task = {'id': 1, 'description': 'Teste'}
    create_task(app, task)
    response = delete_task(app, 1)
    assert response.status_code == 200
    assert len(get_tasks(app).get_json()) == 0

def test_get_task_not_found(app):
    # Caso de erro (task not found)
    response = get_tasks(app)
    assert response.status_code == 404

def test_create_task_invalid_data(app):
    # Caso de erro (invalid data)
    task = {'id': '1', 'description': 'Teste'}
    response = create_task(app, task)
    assert response.status_code == 400