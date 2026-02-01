```python
import pytest
from calculator import Calculator

# Testes Unitários
def test_addition():
    calc = Calculator()
    assert calc.add(2, 3) == 5

def test_subtraction():
    calc = Calculator()
    assert calc.subtract(5, 3) == 2

def test_multiplication():
    calc = Calculator()
    assert calc.multiply(4, 3) == 12

def test_division():
    calc = Calculator()
    assert calc.divide(6, 3) == 2

def test_potenciacao():
    calc = Calculator()
    assert calc.power(2, 3) == 8

def test_raiz_quadrada():
    calc = Calculator()
    assert calc.sqrt(16) == 4

def test_memory_store_and_retrieve():
    calc = Calculator()
    calc.memory_store(5)
    assert calc.memory_recall() == 5

def test_history_operations():
    calc = Calculator()
    calc.add(2, 3)
    calc.subtract(5, 3)
    assert calc.history() == ['2 + 3 = 5', '5 - 3 = 2']

def test_division_by_zero():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.divide(10, 0)

def test_invalid_input_addition():
    calc = Calculator()
    with pytest.raises(TypeError):
        calc.add('a', 3)

def test_invalid_input_subtraction():
    calc = Calculator()
    with pytest.raises(TypeError):
        calc.subtract('a', 3)

def test_invalid_input_multiplication():
    calc = Calculator()
    with pytest.raises(TypeError):
        calc.multiply('a', 3)

def test_invalid_input_division():
    calc = Calculator()
    with pytest.raises(TypeError):
        calc.divide('a', 3)

def test_invalid_input_potenciacao():
    calc = Calculator()
    with pytest.raises(TypeError):
        calc.power('a', 3)

def test_invalid_input_raiz_quadrada():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.sqrt(-4)
```