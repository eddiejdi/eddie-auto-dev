import pytest

class Calculadora:
    def __init__(self):
        self.resultado = 0

    def adicionar(self, num):
        try:
            self.resultado += num
            return f"Adição realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"

    def subtrair(self, num):
        try:
            self.resultado -= num
            return f"Subtração realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"

    def multiplicar(self, num):
        try:
            self.resultado *= num
            return f"Multiplicação realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"

    def dividir(self, num):
        try:
            if num == 0:
                raise ValueError("Divisão por zero não é permitida")
            self.resultado /= num
            return f"Divisão realizada: {self.resultado}"
        except TypeError as e:
            return f"Erro: {e}"
        except ValueError as e:
            return f"Erro: {e}"

def test_adicionar():
    calc = Calculadora()
    assert calc.adicionar(5) == "Adição realizada: 5"
    assert calc.adicionar(-3) == "Adição realizada: 2"

def test_subtrair():
    calc = Calculadora()
    assert calc.subtrair(10) == "Subtração realizada: 10"
    assert calc.subtrair(7) == "Subtração realizada: 3"

def test_multiplicar():
    calc = Calculadora()
    assert calc.multiplicar(4) == "Multiplicação realizada: 4"
    assert calc.multiplicar(-2) == "Multiplicação realizada: -8"

def test_dividir():
    calc = Calculadora()
    assert calc.dividir(6) == "Divisão realizada: 1.0"
    with pytest.raises(ValueError):
        calc.dividir(0)