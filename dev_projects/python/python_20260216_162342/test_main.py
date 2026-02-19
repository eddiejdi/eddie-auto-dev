import pytest
from your_module import Product, main

def test_create_product():
    # Caso de sucesso com valores válidos
    product = Product("Laptop", 1200.0)
    assert str(product) == "Laptop - R$1,200.00"

    # Caso de erro (divisão por zero)
    with pytest.raises(ValueError):
        main(["create", "--name", "Laptop", "--price", "0"])

    # Caso de erro (valores inválidos)
    with pytest.raises(ValueError):
        main(["create", "--name", "Laptop", "--price", "-1200.0"])

def test_list_products():
    # Caso de sucesso com valores válidos
    products = [Product("Laptop", 1200.0), Product("Smartphone", 700.0)]
    for product in products:
        assert str(product) == "Laptop - R$1,200.00"

    # Caso de erro (valores inválidos)
    with pytest.raises(ValueError):
        main(["list"])

def test_main():
    # Caso de sucesso com valores válidos
    result = main(["create", "--name", "Laptop", "--price", "1200.0"])
    assert result == "Product created: Laptop - R$1,200.00"

    # Caso de erro (valores inválidos)
    with pytest.raises(ValueError):
        result = main(["create", "--name", "Laptop", "--price", "-1200.0"])

    # Caso de erro (divisão por zero)
    with pytest.raises(ValueError):
        result = main(["list"])