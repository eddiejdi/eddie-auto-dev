import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome
        self.status = "pendente"

    def marcar_completa(self):
        self.status = "concluída"

    def __str__(self):
        return f"Tarefa: {self.nome} - Status: {self.status}"

def main():
    tarefa1 = Tarefa("Tarefa 1")
    print(tarefa1)

    tarefa1.marcar_completa()
    print(tarefa1)

if __name__ == "__main__":
    main()

def test_tarefa_inicializada():
    tarefa = Tarefa("Teste")
    assert tarefa.nome == "Teste"
    assert tarefa.status == "pendente"

def test_marcar_completa():
    tarefa = Tarefa("Teste")
    tarefa.marcar_completa()
    assert tarefa.status == "concluída"

def test_marcar_completa_status_inicial():
    tarefa = Tarefa("Teste")
    assert tarefa.status == "pendente"
    tarefa.marcar_completa()
    assert tarefa.status == "concluída"

def test_marcar_completa_status_invalido():
    tarefa = Tarefa("Teste")
    with pytest.raises(ValueError):
        tarefa.marcar_completa()

def test_marcar_completa_status_none():
    tarefa = Tarefa("Teste")
    with pytest.raises(TypeError):
        tarefa.marcar_completa(None)

def test_marcar_completa_status_string():
    tarefa = Tarefa("Teste")
    with pytest.raises(ValueError):
        tarefa.marcar_completa("concluída")

def test_str_tarefa():
    tarefa = Tarefa("Teste")
    assert str(tarefa) == "Tarefa: Teste - Status: pendente"