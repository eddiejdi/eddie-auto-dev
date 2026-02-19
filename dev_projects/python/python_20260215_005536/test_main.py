import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome
        self.status = "pendente"

    def marcar_completa(self):
        self.status = "concluída"

    def __str__(self):
        return f"Tarefa: {self.nome}, Status: {self.status}"

def main():
    tarefa1 = Tarefa("Tarefa 1")
    print(tarefa1)

    try:
        tarefa1.marcar_completa()
        print(tarefa1)
    except Exception as e:
        print(f"Erro ao marcar como concluída: {e}")

if __name__ == "__main__":
    main()

def test_tarefa_inicial():
    tarefa = Tarefa("Tarefa 1")
    assert tarefa.nome == "Tarefa 1"
    assert tarefa.status == "pendente"

def test_marcar_completa():
    tarefa = Tarefa("Tarefa 1")
    tarefa.marcar_completa()
    assert tarefa.status == "concluída"

def test_marcar_completa_exception():
    with pytest.raises(Exception) as e:
        Tarefa("").marcar_completa()
    assert str(e.value) == "Erro ao marcar como concluída: Não é possível marcar uma tarefa sem nome."

def test_str():
    tarefa = Tarefa("Tarefa 1")
    assert str(tarefa) == "Tarefa: Tarefa 1, Status: pendente"