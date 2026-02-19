import pytest

def test_fatorial_positivo():
    assert fatorial(5) == 120

def test_fatorial_zero():
    assert fatorial(0) == 1

def test_fatorial_um():
    assert fatorial(1) == 1

def test_fatorial_negativo():
    with pytest.raises(ValueError):
        fatorial(-1)

def test_fatorial_divisao_pelo_zero():
    with pytest.raises(ValueError):
        fatorial(5) / 0

def test_fatorial_string_vazia():
    with pytest.raises(ValueError):
        fatorial("")

def test_fatorial_none():
    with pytest.raises(ValueError):
        fatorial(None)