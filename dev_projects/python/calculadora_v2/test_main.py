import pytest
from main import Calculator

def test_add():
    calc = Calculator()
    assert calc.add(2, 3) == 5
    assert calc.history[-1] == "2 + 3 = 5"

def test_subtract():
    calc = Calculator()
    assert calc.subtract(5, 3) == 2
    assert calc.history[-1] == "5 - 3 = 2"

def test_multiply():
    calc = Calculator()
    assert calc.multiply(4, 3) == 12
    assert calc.history[-1] == "4 * 3 = 12"

def test_divide():
    calc = Calculator()
    assert calc.divide(6, 3) == 2
    assert calc.history[-1] == "6 / 3 = 2"

def test_divide_by_zero():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.divide(5, 0)

def test_power():
    calc = Calculator()
    assert calc.power(2, 3) == 8
    assert calc.history[-1] == "2 ^ 3 = 8"

def test_sqrt():
    calc = Calculator()
    assert calc.sqrt(4) == 2
    assert calc.history[-1] == "sqrt(4) = 2"

def test_sqrt_negative():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.sqrt(-1)

def test_save_to_memory():
    calc = Calculator()
    calc.save_to_memory(10)
    assert calc.memory == 10
    assert calc.history[-1] == "Memória salva: 10"

def test_recall_from_memory():
    calc = Calculator()
    calc.save_to_memory(20)
    assert calc.recall_from_memory() == 20

def test_recall_from_empty_memory():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.recall_from_memory()

def test_get_history():
    calc = Calculator()
    calc.add(1, 2)
    calc.subtract(3, 1)
    assert calc.get_history() == ["1 + 2 = 3", "3 - 1 = 2"]