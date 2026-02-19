import pytest

class TestTarefa1:
    def test_create_task_success(self):
        task = Tarefa1.create_task(1, "Implement Tarefa 1")
        assert isinstance(task, Tarefa1)
        assert task.task_id == 1
        assert task.description == "Implement Tarefa 1"

    def test_create_task_error(self):
        task = Tarefa1.create_task("invalid", "Invalid Task Description")
        assert task is None

    def test_update_task_success(self):
        task = Tarefa1.create_task(1, "Implement Tarefa 1")
        updated_task = Tarefa1.update_task(1, "Implement Tarefa 1 - Parte 2")
        assert isinstance(updated_task, Tarefa1)
        assert updated_task.task_id == 1
        assert updated_task.description == "Implement Tarefa 1 - Parte 2"

    def test_update_task_error(self):
        task = Tarefa1.create_task(1, "Implement Tarefa 1")
        updated_task = Tarefa1.update_task("invalid", "Invalid Task Description")
        assert updated_task is None

    def test_delete_task_success(self):
        result = Tarefa1.delete_task(1)
        assert result is True

    def test_delete_task_error(self):
        result = Tarefa1.delete_task("invalid")
        assert result is False

    def test_list_tasks_success(self):
        tasks = Tarefa1.list_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) == 2