from flask import Flask, jsonify
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

engine = create_engine('sqlite:///tasks.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

@app.route('/tasks', methods=['GET'])
def get_tasks():
    tasks = session.query(Task).all()
    return jsonify([task.to_dict() for task in tasks])

@app.route('/tasks', methods=['POST'])
def create_task():
    title = request.json.get('title')
    description = request.json.get('description')
    new_task = Task(title=title, description=description)
    session.add(new_task)
    session.commit()
    return jsonify(new_task.to_dict()), 201

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    task = session.query(Task).get_or_404(task_id)
    title = request.json.get('title')
    description = request.json.get('description')
    task.title = title
    task.description = description
    session.commit()
    return jsonify(task.to_dict())

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = session.query(Task).get_or_404(task_id)
    session.delete(task)
    session.commit()
    return '', 204

if __name__ == "__main__":
    app.run(debug=True)