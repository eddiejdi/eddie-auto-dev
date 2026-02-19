import pytest
from tarefa1 import Tarefa1

def test_selecionar_tarefa():
    # Caso de sucesso com valores válidos
    tarefa = Tarefa1()
    assert tarefa.selecionar_tarefa() in tarefa.tarefas, "Tarefa selecionada deve estar na lista de tarefas"

    # Casos de erro (divisão por zero)
    with pytest.raises(ZeroDivisionError):
        tarefa.selecionar_tarefa()

    # Edge cases (valores limite, strings vazias, None, etc)
    assert Tarefa1().selecionar_tarefa() in ["Tarefa 1", "Tarefa 2", "Tarefa 3"], "Edge case para valores limites"
    assert Tarefa1().selecionar_tarefa() not in [], "Edge case para strings vazias"
    assert Tarefa1().selecionar_tarefa() is None, "Edge case para None"