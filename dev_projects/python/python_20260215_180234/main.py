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