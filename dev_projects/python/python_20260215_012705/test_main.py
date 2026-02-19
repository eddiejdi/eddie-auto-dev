import pytest
from flask import Flask, request, jsonify

app = Flask(__name__)

# Simulando um banco de dados em memória
data = []

@app.route('/task', methods=['POST'])
def create_task():
    try:
        task = request.get_json()
        data.append(task)
        return jsonify({"message": "Task created successfully", "task": task}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tasks', methods=['GET'])
def get_tasks():
    try:
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

# Testes unitários para a função create_task
def test_create_task_success():
    # Caso de sucesso com valores válidos
    task = {"title": "Test Task", "description": "This is a test task"}
    response = create_task(task)
    assert response.status_code == 201
    assert 'task' in response.json()
    assert response.json()['task'] == task

def test_create_task_division_by_zero():
    # Caso de erro (divisão por zero)
    data.append({"title": "Test Task", "description": "This is a test task"})
    with pytest.raises(Exception) as e:
        create_task(data[0])
    assert str(e.value) == "Cannot divide by zero"

def test_create_task_invalid_data():
    # Caso de erro (valores inválidos)
    data.append({"title": "Test Task", "description": 123})
    with pytest.raises(Exception) as e:
        create_task(data[0])
    assert str(e.value) == "Invalid task data"

def test_create_task_edge_case():
    # Caso de edge case (valores limite)
    data.append({"title": "Test Task", "description": "This is a test task"})
    response = create_task(data[0])
    assert response.status_code == 201
    assert 'task' in response.json()
    assert response.json()['task'] == data[0]

# Testes unitários para a função get_tasks
def test_get_tasks_success():
    # Caso de sucesso com valores válidos
    task = {"title": "Test Task", "description": "This is a test task"}
    create_task(task)
    response = get_tasks()
    assert response.status_code == 200
    assert 'tasks' in response.json()

def test_get_tasks_empty():
    # Caso de erro (banco de dados vazio)
    response = get_tasks()
    assert response.status_code == 200
    assert not response.json()['tasks']

def test_get_tasks_edge_case():
    # Caso de edge case (string vazia)
    data.append({"title": "Test Task", "description": "This is a test task"})
    create_task(data[0])
    response = get_tasks()
    assert 'tasks' in response.json()
    assert len(response.json()['tasks']) == 1