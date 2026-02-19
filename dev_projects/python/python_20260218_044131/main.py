from flask import Flask, request, jsonify, make_response
import sqlite3

app = Flask(__name__)

# Conectar ao banco de dados (criar se não existir)
conn = sqlite3.connect('items.db')
c = conn.cursor()

# Criar tabela se ela não existir
c.execute('''CREATE TABLE IF NOT EXISTS items
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL)''')

conn.commit()

@app.route('/items', methods=['POST'])
def add_item():
    data = request.get_json()
    if not data or 'name' not in data:
        return make_response(jsonify({'error': 'Invalid request'}), 400)

    c.execute('INSERT INTO items (name) VALUES (?)', (data['name'],))
    conn.commit()

    item_id = c.lastrowid
    return jsonify({'message': f'Item {item_id} added successfully'})

@app.route('/items', methods=['GET'])
def list_items():
    c.execute('SELECT * FROM items')
    items = [{'id': row[0], 'name': row[1]} for row in c.fetchall()]
    return jsonify(items)

@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    c.execute('DELETE FROM items WHERE id = ?', (item_id,))
    conn.commit()

    if c.rowcount == 0:
        return make_response(jsonify({'error': 'Item not found'}), 404)
    else:
        return jsonify({'message': f'Item {item_id} deleted successfully'})

if __name__ == "__main__":
    app.run(debug=True)