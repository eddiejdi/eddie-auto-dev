import pytest

class Tarefa:
    def __init__(self, nome):
        self.nome = nome
        self.status = "pendente"

    def marcar_como_concluida(self):
        self.status = "concluída"

def main():
    tarefa1 = Tarefa("Tarefa 1")
    print(f"Tarefa: {tarefa1.nome}, Status: {tarefa1.status}")

    try:
        tarefa1.marcar_como_concluida()
        print(f"Tarefa: {tarefa1.nome}, Status: {tarefa1.status}")
    except Exception as e:
        print(f"Erro ao marcar como concluída: {e}")

if __name__ == "__main__":
    main()

def test_tarefa_init():
    tarefa = Tarefa("Tarefa 1")
    assert tarefa.nome == "Tarefa 1"
    assert tarefa.status == "pendente"

def test_tarefa_marcar_como_concluida():
    tarefa = Tarefa("Tarefa 1")
    tarefa.marcar_como_concluida()
    assert tarefa.status == "concluída"

def test_tarefa_marcar_como_concluida_divisao_por_zero():
    with pytest.raises(Exception) as e:
        Tarefa("Tarefa 1").marcar_como_concluida(0)
    assert str(e.value) == "Erro ao marcar como concluída: divisão por zero"

def test_tarefa_marcar_como_concluida_status_invalido():
    tarefa = Tarefa("Tarefa 1")
    with pytest.raises(Exception) as e:
        tarefa.marcar_como_concluida("invalido")
    assert str(e.value) == "Erro ao marcar como concluída: status invalido"

def test_tarefa_marcar_como_concluida_status_none():
    tarefa = Tarefa("Tarefa 1")
    with pytest.raises(Exception) as e:
        tarefa.marcar_como_concluida(None)
    assert str(e.value) == "Erro ao marcar como concluída: status None"

def test_tarefa_marcar_como_concluida_status_string_vazia():
    tarefa = Tarefa("Tarefa 1")
    with pytest.raises(Exception) as e:
        tarefa.marcar_como_concluida("")
    assert str(e.value) == "Erro ao marcar como concluída: status string vazia"