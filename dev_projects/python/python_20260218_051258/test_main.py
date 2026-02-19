import unittest

class Tarefa1:
    def __init__(self):
        self.tarefas = []

    def adicionar_tarefa(self, tarefa):
        if isinstance(tarefa, str):
            self.tarefas.append(tarefa)
        else:
            raise ValueError("Tarefa deve ser uma string")

    def listar_tarefas(self):
        return self.tarefas

    def remover_tarefa(self, index):
        if 0 <= index < len(self.tarefas):
            del self.tarefas[index]
        else:
            raise IndexError("Índice inválido")

class TestTarefa1(unittest.TestCase):
    def setUp(self):
        self.tarefa1 = Tarefa1()

    def test_adicionar_tarefa(self):
        self.tarefa1.adicionar_tarefa("Fazer compras")
        self.assertEqual(["Fazer compras"], self.tarefa1.listar_tarefas())

    def test_remover_tarefa(self):
        self.tarefa1.adicionar_tarefa("Fazer compras")
        self.tarefa1.remover_tarefa(0)
        self.assertEqual([], self.tarefa1.listar_tarefas())