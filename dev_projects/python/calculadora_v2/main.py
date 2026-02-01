import math


class Calculator:
    def __init__(self):
        self.memory = 0
        self.history = []

    def add(self, a: float, b: float) -> float:
        """Soma dois números."""
        result = a + b
        self.history.append(f"{self._fmt(a)} + {self._fmt(b)} = {self._fmt(result)}")
        return result

    def subtract(self, a: float, b: float) -> float:
        """Subtrai dois números."""
        result = a - b
        self.history.append(f"{self._fmt(a)} - {self._fmt(b)} = {self._fmt(result)}")
        return result

    def multiply(self, a: float, b: float) -> float:
        """Multiplica dois números."""
        result = a * b
        self.history.append(f"{self._fmt(a)} * {self._fmt(b)} = {self._fmt(result)}")
        return result

    def divide(self, a: float, b: float) -> float:
        """Divide dois números."""
        if b == 0:
            raise ValueError("Divisão por zero não é permitida.")
        result = a / b
        self.history.append(f"{self._fmt(a)} / {self._fmt(b)} = {self._fmt(result)}")
        return result

    def power(self, base: float, exponent: float) -> float:
        """Calcula a potência de um número."""
        result = math.pow(base, exponent)
        self.history.append(
            f"{self._fmt(base)} ^ {self._fmt(exponent)} = {self._fmt(result)}"
        )
        return result

    def sqrt(self, number: float) -> float:
        """Calcula a raiz quadrada de um número."""
        if number < 0:
            raise ValueError(
                "Não é possível calcular a raiz quadrada de um número negativo."
            )
        result = math.sqrt(number)
        self.history.append(f"sqrt({self._fmt(number)}) = {self._fmt(result)}")
        return result

    def save_to_memory(self, value: float) -> None:
        """Salva o valor na memória."""
        self.memory = value
        self.history.append(f"Memória salva: {self._fmt(value)}")

    def recall_from_memory(self) -> float:
        """Recupera o valor da memória."""
        if self.memory == 0:
            raise ValueError("A memória está vazia.")
        return self.memory

    def get_history(self) -> list:
        """Retorna o histórico de operações."""
        return self.history

    def _fmt(self, v: float) -> str:
        """Format number: omit .0 for integers, keep decimals otherwise."""
        try:
            if float(v).is_integer():
                return str(int(float(v)))
        except Exception:
            pass
        return str(v)


def main():
    calc = Calculator()
    while True:
        print("\nCalculadora CLI")
        print("1. Soma")
        print("2. Subtração")
        print("3. Multiplicação")
        print("4. Divisão")
        print("5. Potenciação")
        print("6. Raiz Quadrada")
        print("7. Salvar na Memória")
        print("8. Recuperar da Memória")
        print("9. Histórico de Operações")
        print("0. Sair")
        choice = input("Escolha uma opção: ")

        if choice == "0":
            break
        elif choice in ["1", "2", "3", "4", "5"]:
            a = float(input("Digite o primeiro número: "))
            b = float(input("Digite o segundo número: "))
            if choice == "1":
                print(f"Resultado: {calc.add(a, b)}")
            elif choice == "2":
                print(f"Resultado: {calc.subtract(a, b)}")
            elif choice == "3":
                print(f"Resultado: {calc.multiply(a, b)}")
            elif choice == "4":
                try:
                    print(f"Resultado: {calc.divide(a, b)}")
                except ValueError as e:
                    print(e)
            else:
                exponent = float(input("Digite o expoente: "))
                print(f"Resultado: {calc.power(a, exponent)}")
        elif choice == "6":
            number = float(input("Digite o número: "))
            try:
                print(f"Resultado: {calc.sqrt(number)}")
            except ValueError as e:
                print(e)
        elif choice == "7":
            value = float(input("Digite o valor para salvar na memória: "))
            calc.save_to_memory(value)
        elif choice == "8":
            try:
                print(f"Valor da Memória: {calc.recall_from_memory()}")
            except ValueError as e:
                print(e)
        elif choice == "9":
            for entry in calc.get_history():
                print(entry)


if __name__ == "__main__":
    main()
