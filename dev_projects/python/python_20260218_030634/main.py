# Importações necessárias
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Conexão ao banco de dados SQLite (criado se não existir)
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Criação da tabela 'tasks' se ela não existir
c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed BOOLEAN DEFAULT FALSE
            )''')

conn.commit()

@app.route('/tasks', methods=['GET'])
def get_tasks():
    c.execute('SELECT * FROM tasks')
    tasks = c.fetchall()
    return jsonify([{'id': task[0], 'title': task[1], 'description': task[2], 'completed': task[3]} for task in tasks])

@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    c.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = c.fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({'id': task[0], 'title': task[1], 'description': task[2], 'completed': task[3]})

@app.route('/tasks', methods=['POST'])
def create_task():
    title = request.json.get('title')
    description = request.json.get('description')
    c.execute('INSERT INTO tasks (title, description) VALUES (?, ?)', (title, description))
    conn.commit()
    return jsonify({'id': c.lastrowid, 'title': title, 'description': description}), 201

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    title = request.json.get('title')
    description = request.json.get('description')
    c.execute('UPDATE tasks SET title = ?, description = ? WHERE id = ?', (title, description, task_id))
    conn.commit()
    return jsonify({'id': task_id, 'title': title, 'description': description})

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    return jsonify({'message': 'Task deleted'})

if __name__ == "__main__":
    app.run(debug=True)