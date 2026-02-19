import pytest
from product import Product, generate_products

def test_product_init():
    # Teste para inicialização do objeto Product com valores válidos
    name = "Produto 1"
    price = 10.5
    product = Product(name, price)
    assert product.name == name
    assert product.price == price

def test_generate_products_success():
    # Teste para gerar produtos com sucesso
    n = 5
    products = generate_products(n)
    assert len(products) == n
    for product in products:
        assert isinstance(product, Product)

def test_generate_products_failure():
    # Teste para gerar produtos com erro (n <= 0)
    with pytest.raises(ValueError):
        generate_products(0)

def test_product_repr():
    # Teste para representação do objeto Product
    name = "Produto 1"
    price = 10.5
    product = Product(name, price)
    assert str(product) == f"Product(name={name}, price={price})"