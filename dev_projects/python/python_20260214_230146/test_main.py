import pytest
from flask import Flask, jsonify, request
import json

app = Flask(__name__)

# Simulação de um banco de dados em memória
tasks = []

@app.route('/tasks', methods=['GET'])
def get_tasks():
    try:
        return jsonify(tasks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks', methods=['POST'])
def create_task():
    try:
        task = request.get_json()
        tasks.append(task)
        return jsonify(task), 201
    except json.JSONDecodeError as e:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        task = request.get_json()
        tasks[task_id] = task
        return jsonify(tasks[task_id])
    except IndexError as e:
        return jsonify({'error': 'Task not found'}), 404
    except json.JSONDecodeError as e:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        del tasks[task_id]
        return jsonify({'message': 'Task deleted'})
    except IndexError as e:
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

# Testes unitários

def test_get_tasks_success():
    # Simula um banco de dados com alguns itens
    tasks = [{'id': 1, 'title': 'Task 1'}, {'id': 2, 'title': 'Task 2'}]
    
    # Envia uma requisição GET para a rota /tasks
    response = app.test_client().get('/tasks')
    
    # Verifica se o status da resposta é 200 (OK)
    assert response.status_code == 200
    
    # Verifica se a resposta contém os itens corretos
    assert json.loads(response.data) == tasks

def test_get_tasks_error():
    # Envia uma requisição GET para a rota /tasks sem autorização
    response = app.test_client().get('/tasks', headers={'Authorization': 'Bearer invalid_token'})
    
    # Verifica se o status da resposta é 401 (Unauthorized)
    assert response.status_code == 401

def test_create_task_success():
    # Envia uma requisição POST para a rota /tasks com um item válido
    task = {'title': 'New Task'}
    response = app.test_client().post('/tasks', json=task, headers={'Content-Type': 'application/json'})
    
    # Verifica se o status da resposta é 201 (Created)
    assert response.status_code == 201
    
    # Verifica se a resposta contém os itens corretos
    new_task = json.loads(response.data)
    assert new_task['title'] == 'New Task'

def test_create_task_error():
    # Envia uma requisição POST para a rota /tasks com um item inválido
    task = {'title': ''}
    response = app.test_client().post('/tasks', json=task, headers={'Content-Type': 'application/json'})
    
    # Verifica se o status da resposta é 400 (Bad Request)
    assert response.status_code == 400

def test_update_task_success():
    # Simula um banco de dados com alguns itens
    tasks = [{'id': 1, 'title': 'Task 1'}, {'id': 2, 'title': 'Task 2'}]
    
    # Envia uma requisição PUT para a rota /tasks/1 com um item válido
    task = {'title': 'Updated Task'}
    response = app.test_client().put('/tasks/1', json=task, headers={'Content-Type': 'application/json'})
    
    # Verifica se o status da resposta é 200 (OK)
    assert response.status_code == 200
    
    # Verifica se a resposta contém os itens corretos
    updated_task = json.loads(response.data)
    assert updated_task['title'] == 'Updated Task'

def test_update_task_error():
    # Envia uma requisição PUT para a rota /tasks/1 com um item inválido
    task = {'title': ''}
    response = app.test_client().put('/tasks/1', json=task, headers={'Content-Type': 'application/json'})
    
    # Verifica se o status da resposta é 400 (Bad Request)
    assert response.status_code == 400

def test_delete_task_success():
    # Simula um banco de dados com alguns itens
    tasks = [{'id': 1, 'title': 'Task 1'}, {'id': 2, 'title': 'Task 2'}]
    
    # Envia uma requisição DELETE para a rota /tasks/1
    response = app.test_client().delete('/tasks/1')
    
    # Verifica se o status da resposta é 200 (OK)
    assert response.status_code == 200
    
    # Verifica se a resposta contém uma mensagem de sucesso
    assert json.loads(response.data) == {'message': 'Task deleted'}

def test_delete_task_error():
    # Envia uma requisição DELETE para a rota /tasks/1 sem autorização
    response = app.test_client().delete('/tasks/1', headers={'Authorization': 'Bearer invalid_token'})
    
    # Verifica se o status da resposta é 401 (Unauthorized)
    assert response.status_code == 401