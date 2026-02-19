import pytest
from flask import Flask, request, jsonify, abort
from flask_httpauth import HTTPBasicAuth

app = Flask(__name__)
auth = HTTPBasicAuth()

# Dados de autenticação fictícios
USERS = {
    "user1": "password1",
    "user2": "password2"
}

@app.route('/api/task', methods=['GET'])
@auth.login_required
def get_task():
    task_id = request.args.get('id')
    if not task_id:
        abort(400, 'Task ID is required')

    # Simulação de busca de tarefa por ID
    task = {
        "id": task_id,
        "description": "Example task",
        "status": "pending"
    }

    return jsonify(task)

@app.route('/api/task', methods=['POST'])
@auth.login_required
def create_task():
    data = request.get_json()
    if not data or 'description' not in data:
        abort(400, 'Description is required')

    # Simulação de criação de tarefa
    task_id = len(USERS) + 1
    task = {
        "id": task_id,
        "description": data['description'],
        "status": "pending"
    }

    USERS[f"user{task_id}"] = task

    return jsonify(task), 201

@app.route('/api/task/<int:task_id>', methods=['PUT'])
@auth.login_required
def update_task(task_id):
    if not task_id:
        abort(400, 'Task ID is required')

    # Simulação de atualização de tarefa por ID
    task = USERS.get(f"user{task_id}")
    if not task:
        abort(404, f"Task with ID {task_id} does not exist")

    data = request.get_json()
    if not data or 'description' in data:
        abort(400, 'Description is required')

    task['description'] = data['description']
    task['status'] = "in progress"

    return jsonify(task)

@app.route('/api/task/<int:task_id>', methods=['DELETE'])
@auth.login_required
def delete_task(task_id):
    if not task_id:
        abort(400, 'Task ID is required')

    # Simulação de deleção de tarefa por ID
    task = USERS.get(f"user{task_id}")
    if not task:
        abort(404, f"Task with ID {task_id} does not exist")

    del USERS[f"user{task_id}"]

    return jsonify({"message": "Task deleted"}), 204

@app.route('/api/auth', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')

    if username in USERS and USERS[username] == password:
        token = f"Bearer {username}"
        return jsonify({"token": token}), 200
    else:
        abort(401, 'Invalid credentials')

if __name__ == '__main__':
    app.run(debug=True)