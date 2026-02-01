import pytest
from main import Calculator


def test_add():
    calc = Calculator()
    assert calc.add(2, 3) == 5
    assert calc.add(-1, -1) == -2
    assert calc.add(0, 0) == 0


def test_subtract():
    calc = Calculator()
    assert calc.subtract(5, 2) == 3
    assert calc.subtract(7, 4) == 3
    assert calc.subtract(0, 0) == 0


def test_multiply():
    calc = Calculator()
    assert calc.multiply(3, 4) == 12
    assert calc.multiply(-2, -2) == 4
    assert calc.multiply(0, 5) == 0


def test_divide():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.divide(10, 0)
    assert calc.divide(8, 2) == 4
    assert calc.divide(-3, -3) == 1


def test_power():
    calc = Calculator()
    assert math.isclose(calc.power(2, 3), 8, rel_tol=1e-9)
    assert math.isclose(calc.power(5, 0), 1, rel_tol=1e-9)
    assert math.isclose(calc.power(-2, 3), -8, rel_tol=1e-9)


def test_sqrt():
    calc = Calculator()
    with pytest.raises(ValueError):
        calc.sqrt(-4)
    assert math.isclose(calc.sqrt(16), 4, rel_tol=1e-9)


def test_store():
    calc = Calculator()
    calc.store(5)
    assert calc.recall() == 5


def test_clear_memory():
    calc = Calculator()
    calc.store(3)
    calc.clear_memory()
    assert not calc.memory
    assert not calc.history


def test_display_history():
    calc = Calculator()
    calc.add(1, 2)
    calc.subtract(4, 2)
    calc.multiply(5, 3)
    with pytest.raises(ValueError):
        calc.display_history()


if __name__ == "__main__":
    pytest.main()
