import math

class Calculator:
    def __init__(self):
        self.memory = []
        self.history = []

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Divisão por zero não é permitida")
        return a / b

    def power(self, base, exponent):
        return math.pow(base, exponent)

    def sqrt(self, number):
        if number < 0:
            raise ValueError("Raiz quadrada de um número negativo não é permitida")
        return math.sqrt(number)

    def store(self, value):
        self.memory.append(value)
        self.history.append(f"Stored: {value}")

    def recall(self):
        if not self.memory:
            return "Memória vazia"
        return self.memory[-1]

    def clear_memory(self):
        self.memory.clear()
        self.history.clear()

    def display_history(self):
        raise ValueError("Display history is not available in test mode")

if __name__ == "__main__":
    calc = Calculator()

    while True:
        print("\nCalculator Menu:")
        print("1. Add")
        print("2. Subtract")
        print("3. Multiply")
        print("4. Divide")
        print("5. Power")
        print("6. Square Root")
        print("7. Store")
        print("8. Recall")
        print("9. Clear Memory")
        print("10. Display History")
        print("11. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            a = float(input("Enter first number: "))
            b = float(input("Enter second number: "))
            result = calc.add(a, b)
            print(f"Result: {result}")
            calc.history.append(f"{a} + {b} = {result}")

        elif choice == '2':
            a = float(input("Enter first number: "))
            b = float(input("Enter second number: "))
            result = calc.subtract(a, b)
            print(f"Result: {result}")
            calc.history.append(f"{a} - {b} = {result}")

        elif choice == '3':
            a = float(input("Enter first number: "))
            b = float(input("Enter second number: "))
            result = calc.multiply(a, b)
            print(f"Result: {result}")
            calc.history.append(f"{a} * {b} = {result}")

        elif choice == '4':
            a = float(input("Enter first number: "))
            b = float(input("Enter second number: "))
            try:
                result = calc.divide(a, b)
                print(f"Result: {result}")
                calc.history.append(f"{a} / {b} = {result}")
            except ValueError as e:
                print(e)

        elif choice == '5':
            base = float(input("Enter base number: "))
            exponent = float(input("Enter exponent: "))
            result = calc.power(base, exponent)
            print(f"Result: {result}")
            calc.history.append(f"{base} ** {exponent} = {result}")

        elif choice == '6':
            number = float(input("Enter a number: "))
            result = calc.sqrt(number)
            print(f"Result: {result}")
            calc.history.append(f"sqrt({number}) = {result}")

        elif choice == '7':
            value = float(input("Enter a value to store: "))
            calc.store(value)

        elif choice == '8':
            if not calc.memory:
                print("Memory is empty")
            else:
                print(f"Recalled value: {calc.recall()}")

        elif choice == '9':
            calc.clear_memory()

        elif choice == '10':
            calc.display_history()

        elif choice == '11':
            print("Exiting calculator...")
            break

        else:
            print("Invalid choice. Please try again.")