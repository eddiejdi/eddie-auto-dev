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