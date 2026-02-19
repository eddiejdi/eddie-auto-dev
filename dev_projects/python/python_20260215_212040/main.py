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