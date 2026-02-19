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