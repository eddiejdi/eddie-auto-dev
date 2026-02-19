import pytest

class TestTarefa1:
    def setup_method(self):
        self.tarefa1 = Tarefa1()

    @pytest.mark.parametrize("task", ["Task 1", "Task 2"])
    def test_add_task_success(self, task):
        self.tarefa1.add_task(task)
        assert task in self.tarefa1.task_list

    @pytest.mark.parametrize("task", ["Task 3", "Task 4"])
    def test_remove_task_success(self, task):
        self.tarefa1.add_task(task)
        self.tarefa1.remove_task(task)
        assert task not in self.tarefa1.task_list

    @pytest.mark.parametrize("index", [0, 1])
    def test_execute_task_success(self, index):
        task = self.tarefa1.task_list[index]
        self.tarefa1.execute_task(index)
        assert "Executing task" in self.tarefa1.output

    @pytest.mark.parametrize("task", ["Task 5", "Task 6"])
    def test_add_task_error(self, task):
        with pytest.raises(Exception) as e:
            self.tarefa1.add_task(task)
        assert str(e.value).startswith("Error adding task")

    @pytest.mark.parametrize("task", ["Task 7", "Task 8"])
    def test_remove_task_error(self, task):
        with pytest.raises(Exception) as e:
            self.tarefa1.remove_task(task)
        assert str(e.value).startswith("Error removing task")

    @pytest.mark.parametrize("index", [-1, len(self.tarefa1.task_list)])
    def test_execute_task_error(self, index):
        with pytest.raises(Exception) as e:
            self.tarefa1.execute_task(index)
        assert str(e.value).startswith("Invalid task index")