from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Conexão com o banco de dados SQLite
conn = sqlite3.connect('scrum.db')
c = conn.cursor()

# Criando a tabela se ela não existir
c.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT)''')

@app.route('/tasks', methods=['GET'])
def get_tasks():
    try:
        c.execute('SELECT * FROM tasks')
        tasks = c.fetchall()
        return jsonify([{'id': task[0], 'title': task[1], 'description': task[2]} for task in tasks])
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks', methods=['POST'])
def create_task():
    try:
        title = request.json.get('title')
        description = request.json.get('description')
        if not title or not description:
            return jsonify({'error': 'Title and description are required'}), 400
        c.execute('INSERT INTO tasks (title, description) VALUES (?, ?)', (title, description))
        conn.commit()
        return jsonify({'id': c.lastrowid, 'title': title, 'description': description}), 201
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        title = request.json.get('title')
        description = request.json.get('description')
        if not title and not description:
            return jsonify({'error': 'Title and description are required'}), 400
        c.execute('UPDATE tasks SET title=?, description=? WHERE id=?', (title, description, task_id))
        conn.commit()
        return jsonify({'id': task_id, 'title': title, 'description': description}), 200
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        c.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        conn.commit()
        return jsonify({'message': 'Task deleted'}), 204
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)