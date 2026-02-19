import argparse

class Product:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def __str__(self):
        return f"{self.name} - R${self.price:.2f}"

def main():
    parser = argparse.ArgumentParser(description="Product Manager")
    parser.add_argument("action", choices=["create", "list"], help="Action to perform")
    parser.add_argument("--name", required=True, help="Name of the product")
    parser.add_argument("--price", type=float, required=True, help="Price of the product")

    args = parser.parse_args()

    try:
        if args.action == "create":
            product = Product(args.name, args.price)
            print(f"Product created: {product}")
        elif args.action == "list":
            products = [Product("Laptop", 1200.0), Product("Smartphone", 700.0)]
            for product in products:
                print(product)
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()