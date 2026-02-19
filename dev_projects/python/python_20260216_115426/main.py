from flask import Flask, request, jsonify
import uuid

app = Flask(__name__)

tasks = []

@app.route('/tasks', methods=['POST'])
def create_task():
    try:
        task_data = request.get_json()
        if not task_data or 'title' not in task_data:
            return jsonify({'error': 'Invalid task data'}), 400
        
        new_task = {
            'id': str(uuid.uuid4()),
            'title': task_data['title'],
            'status': 'pending'
        }
        
        tasks.append(new_task)
        
        return jsonify(new_task), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks', methods=['GET'])
def list_tasks():
    try:
        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)