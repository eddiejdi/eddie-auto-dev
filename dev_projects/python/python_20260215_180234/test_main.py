import pytest
from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)

# Configuração do banco de dados SQLite
DATABASE = 'scrum.db'
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending'
);
"""

@app.before_first_request
def create_table():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE)
    conn.commit()

# Rota para listar todas as tarefas
@app.route('/tasks', methods=['GET'])
def list_tasks():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    conn.close()
    return jsonify(tasks)

# Rota para adicionar uma nova tarefa
@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    title = data['title']
    description = data.get('description')
    status = data.get('status', 'pending')

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)", (title, description, status))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': task_id}), 201

# Rota para atualizar uma tarefa existente
@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    title = data['title']
    description = data.get('description')
    status = data.get('status', 'pending')

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET title=?, description=?, status=? WHERE id=?", (title, description, status, task_id))
    conn.commit()
    conn.close()
    return jsonify({'id': task_id})

# Rota para deletar uma tarefa existente
@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'id': task_id})

if __name__ == "__main__":
    app.run(debug=True)

# Testes para list_tasks
def test_list_tasks_success():
    # Simula uma requisição GET para listar todas as tarefas
    response = app.test_client().get('/tasks')
    
    # Verifica se a resposta é 200 OK
    assert response.status_code == 200
    
    # Verifica se o corpo da resposta contém um array de tarefas
    tasks = response.json()
    assert isinstance(tasks, list)
    
    # Verifica se cada tarefa tem as propriedades corretas
    for task in tasks:
        assert 'id' in task
        assert 'title' in task
        assert 'description' in task
        assert 'status' in task

def test_list_tasks_error():
    # Simula uma requisição GET para listar todas as tarefas com um erro interno do servidor
    response = app.test_client().get('/tasks')
    
    # Verifica se a resposta é 500 Internal Server Error
    assert response.status_code == 500

# Testes para add_task
def test_add_task_success():
    # Simula uma requisição POST para adicionar uma nova tarefa
    data = {'title': 'Teste', 'description': 'Descrição do teste'}
    response = app.test_client().post('/tasks', json=data)
    
    # Verifica se a resposta é 201 Created e contém o ID da tarefa adicionada
    assert response.status_code == 201
    task_id = response.json()['id']
    assert isinstance(task_id, int)

def test_add_task_error():
    # Simula uma requisição POST para adicionar uma nova tarefa com um campo inválido
    data = {'title': 'Teste', 'description': 'Descrição do teste', 'status': 'invalid'}
    response = app.test_client().post('/tasks', json=data)
    
    # Verifica se a resposta é 400 Bad Request e contém uma mensagem de erro
    assert response.status_code == 400
    assert response.json()['message'] == 'Invalid status value'

# Testes para update_task
def test_update_task_success():
    # Simula uma requisição PUT para atualizar uma tarefa existente
    data = {'title': 'Teste', 'description': 'Descrição do teste'}
    response = app.test_client().put('/tasks/1', json=data)
    
    # Verifica se a resposta é 200 OK e contém o ID da tarefa atualizada
    assert response.status_code == 200
    task_id = response.json()['id']
    assert isinstance(task_id, int)

def test_update_task_error():
    # Simula uma requisição PUT para atualizar uma tarefa inexistente
    data = {'title': 'Teste', 'description': 'Descrição do teste'}
    response = app.test_client().put('/tasks/999', json=data)
    
    # Verifica se a resposta é 404 Not Found e contém uma mensagem de erro
    assert response.status_code == 404
    assert response.json()['message'] == 'Task not found'

# Testes para delete_task
def test_delete_task_success():
    # Simula uma requisição DELETE para deletar uma tarefa existente
    response = app.test_client().delete('/tasks/1')
    
    # Verifica se a resposta é 200 OK e contém o ID da tarefa removida
    assert response.status_code == 200
    task_id = response.json()['id']
    assert isinstance(task_id, int)

def test_delete_task_error():
    # Simula uma requisição DELETE para deletar uma tarefa inexistente
    response = app.test_client().delete('/tasks/999')
    
    # Verifica se a resposta é 404 Not Found e contém uma mensagem de erro
    assert response.status_code == 404
    assert response.json()['message'] == 'Task not found'