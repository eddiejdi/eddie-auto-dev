import pytest

class TestTarefa1:
    def test_set_feature1(self):
        tarefa1 = Tarefa1()
        tarefa1.set_feature1("feature1")
        assert tarefa1.get_feature1() == "feature1", "Feature1 não foi setada corretamente"

    def test_get_feature1(self):
        tarefa1 = Tarefa1()
        tarefa1.set_feature1("feature1")
        assert tarefa1.get_feature1() == "feature1", "Feature1 não foi recuperada corretamente"