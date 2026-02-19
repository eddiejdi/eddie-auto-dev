import pytest

class TestProduct:
    def test_init(self):
        product = Product("Laptop", 1200.0)
        assert product.name == "Laptop"
        assert product.price == 1200.0

    def test_add_item(self, cart):
        product = Product("Mouse", 50.0)
        cart.add_item(product)
        assert len(cart.items) == 1
        assert cart.items[0] == product

class TestShoppingCart:
    @pytest.fixture
    def cart(self):
        return ShoppingCart()

    def test_add_item(self, cart):
        product = Product("Laptop", 1200.0)
        cart.add_item(product)
        assert len(cart.items) == 1
        assert cart.items[0] == product

    def test_remove_item(self, cart):
        product = Product("Mouse", 50.0)
        cart.add_item(product)
        cart.remove_item(product)
        assert len(cart.items) == 0

    def test_calculate_total(self, cart):
        product1 = Product("Laptop", 1200.0)
        product2 = Product("Mouse", 50.0)
        cart.add_item(product1)
        cart.add_item(product2)
        assert round(cart.calculate_total(), 2) == 1250.0

class TestShoppingCartCLI:
    def test_add_product(self, cli):
        cli.add_product("Laptop", 1200.0)
        assert len(cli.cart.items) == 1
        assert cli.cart.items[0].name == "Laptop"
        assert cli.cart.items[0].price == 1200.0

    def test_remove_product(self, cli):
        cli.add_product("Mouse", 50.0)
        cli.remove_product("Mouse")
        assert len(cli.cart.items) == 0

    def test_calculate_total(self, cli):
        cli.add_product("Laptop", 1200.0)
        cli.add_product("Mouse", 50.0)
        assert round(cli.calculate_total(), 2) == 1250.0