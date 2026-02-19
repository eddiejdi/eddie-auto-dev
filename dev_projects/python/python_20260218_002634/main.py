from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# Conexão ao banco de dados (criado se não existir)
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Criação da tabela (se não existir)
cursor.execute('''
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
''')

# Função para listar todos os itens
@app.route('/items', methods=['GET'])
def get_items():
    try:
        cursor.execute('SELECT * FROM items')
        items = cursor.fetchall()
        return jsonify(items), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Função para adicionar um novo item
@app.route('/items', methods=['POST'])
def add_item():
    try:
        data = request.get_json()
        name = data['name']
        cursor.execute('INSERT INTO items (name) VALUES (?)', (name,))
        conn.commit()
        return jsonify({'message': 'Item added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Função para atualizar um item existente
@app.route('/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    try:
        data = request.get_json()
        name = data['name']
        cursor.execute('UPDATE items SET name = ? WHERE id = ?', (name, item_id))
        conn.commit()
        return jsonify({'message': 'Item updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Função para deletar um item
@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    try:
        cursor.execute('DELETE FROM items WHERE id = ?', (item_id,))
        conn.commit()
        return jsonify({'message': 'Item deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)