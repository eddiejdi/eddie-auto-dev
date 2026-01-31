```python
import pytest
from calculator import Calculator  # Supondo que a calculadora esteja em um arquivo chamado calculator.py

def test_addition():
    calc = Calculator()
    result = calc.add(2, 3)
    assert result == 5

def test_subtraction():
    calc = Calculator()
    result = calc.subtract(5, 2)
    assert result == 3

def test_multiplication():
    calc = Calculator()
    result = calc.multiply(4, 3)
    assert result == 12

def test_division():
    calc = Calculator()
    result = calc.divide(10, 2)
    assert result == 5

def test_division_by_zero_error():
    calc = Calculator()
    with pytest.raises(ZeroDivisionError):
        calc.divide(5, 0)

def test_potenciacao():
    calc = Calculator()
    result = calc.power(2, 3)
    assert result == 8

def test_raiz_quadrada():
    calc = Calculator()
    result = calc.sqrt(16)
    assert result == 4

def test_memory_set_and_get():
    calc = Calculator()
    calc.memory_set(5)
    assert calc.memory_get() == 5

def test_history_empty_initially():
    calc = Calculator()
    assert len(calc.history) == 0

def test_history_after_operations():
    calc = Calculator()
    calc.add(2, 3)
    calc.subtract(5, 2)
    assert len(calc.history) == 2

def test_invalid_input_error():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.add("a", 3)

def test_empty_memory_get_error():
    calc = Calculator()
    calc.memory_set(None)
    with pytest.raises(ValueError):
        calc.memory_get()

def test_large_numbers():
    calc = Calculator()
    result = calc.multiply(123456789, 987654321)
    assert result == 121932631112635269

def test_negative_numbers():
    calc = Calculator()
    result = calc.subtract(-5, -2)
    assert result == -3
```