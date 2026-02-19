from typing import List

class Product:
    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price

class ShoppingCart:
    def __init__(self):
        self.items: List[Product] = []

    def add_item(self, product: Product):
        self.items.append(product)

    def remove_item(self, product: Product):
        self.items.remove(product)

    def calculate_total(self) -> float:
        return sum(item.price for item in self.items)

class ShoppingCartCLI:
    def __init__(self):
        self.cart = ShoppingCart()

    def add_product(self, name: str, price: float):
        product = Product(name, price)
        self.cart.add_item(product)

    def remove_product(self, name: str):
        for product in self.cart.items:
            if product.name == name:
                self.cart.remove_item(product)
                break

    def calculate_total(self) -> float:
        return self.cart.calculate_total()

if __name__ == "__main__":
    cli = ShoppingCartCLI()
    cli.add_product("Laptop", 1200.0)
    cli.add_product("Mouse", 50.0)
    print(f"Total: ${cli.calculate_total():.2f}")