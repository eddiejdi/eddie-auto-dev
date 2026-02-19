import random

class Product:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def __repr__(self):
        return f"Product(name={self.name}, price={self.price})"

def generate_products(n):
    products = []
    for _ in range(n):
        name = f"Produto {random.randint(1, 100)}"
        price = random.uniform(1.0, 100.0)
        products.append(Product(name, price))
    return products

def main():
    try:
        n = int(input("Digite o número de produtos a gerar: "))
        if n <= 0:
            raise ValueError("O número de produtos deve ser maior que zero.")
        
        products = generate_products(n)
        print("Lista de produtos:")
        for product in products:
            print(product)
    except ValueError as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    main()