---
description: "Use when: implementing or fixing tests, coverage rules, and pytest policy"
applyTo: "**/*test*,**/conftest*,**/*spec*,**/pytest*"
---

# 🧪 Testes Unitários — Regra Obrigatória Global

**Status**: ⚠️ **CRÍTICO — IMPEDITIVO GLOBAL**  
**Aplicável a**: TODO código novo, correções, features  
**Padrão**: pytest + pytest-cov  
**Cobertura mínima**: 80%

---

## 📋 Regras Obrigatórias

### 1. Toda Correção Precisa de Testes
```python
❌ NUNCA: Correção sem testes
   git commit -m "fix: corrigir bug X"  # SEM testes = REJECT

✅ SEMPRE: Incluir testes na mesma PR/commit
   1. Corrigir código
   2. Escrever testes
   3. pytest --cov=... -q (passar 100%)
   4. git commit -m "fix: corrigir bug X + testes"
```

### 2. Cobertura Mínima: 80%
```bash
# Verificar cobertura
pytest --cov=btc_trading_agent --cov=specialized_agents --cov-report=term-missing

# Output esperado
Name                            Stmts   Miss  Cover   Missing
─────────────────────────────────────────────────────
btc_trading_agent/models.py        120     10    92%
specialized_agents/api.py          200     30    85%
─────────────────────────────────────────────────────
TOTAL                            1000     80    92%  ✅ ACIMA DE 80%
```

### 3. Estrutura de Testes
```
project/
├── btc_trading_agent/
│   ├── __init__.py
│   ├── models.py
│   └── [código]
│
└── btc_trading_agent/tests/        ← Testes devem estar aqui
    ├── __init__.py
    ├── conftest.py                 ← Fixtures compartilhadas
    ├── test_models.py              ← Testes para models.py
    ├── test_api.py
    └── test_trading_logic.py
```

### 4. Padrão de Teste (Pytest)
```python
# tests/test_exemplo.py
import pytest
from modulo import MyClass

@pytest.fixture
def setup():
    """Setup para testes."""
    obj = MyClass()
    return obj

def test_funcionalidade_basica(setup):
    """Testa funcionalidade básica."""
    result = setup.fazer_algo()
    assert result == valor_esperado

def test_erro_esperado(setup):
    """Testa comportamento em erro."""
    with pytest.raises(ValueError):
        setup.fazer_algo_invalido()

@pytest.mark.parametrize("entrada,esperado", [
    ("a", 1),
    ("b", 2),
])
def test_multiplos_casos(entrada, esperado):
    """Testa múltiplos cenários."""
    assert processar(entrada) == esperado
```

### 5. Fixtures Reutilizáveis (conftest.py)
```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Session de banco para testes."""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def mock_trading_api():
    """Mock da API de trading."""
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.fixture
def sample_trade_data():
    """Dados de teste padrão."""
    return {
        "symbol": "BTC-USDT",
        "entry": 45000.0,
        "exit": 46000.0,
        "result": "WIN"
    }
```

### 6. Mocking — IOs Externos
```python
# ✅ Correto: Mock de APIs externas
from unittest.mock import patch, MagicMock

@patch('requests.get')  # Mock HTTP
def test_fetch_price(mock_get):
    mock_get.return_value.json.return_value = {"price": 45000}
    assert fetch_price("BTC") == 45000

@patch('psycopg2.connect')  # Mock DB
def test_database_access(mock_db):
    mock_db.return_value.cursor().fetchall.return_value = [(1, "test")]
    result = query_database()
    assert len(result) == 1

# ❌ Errado: Usar API real em teste
def test_fetch_price_WRONG():
    # NÃO FAÇA ISSO:
    result = requests.get("https://api.realprice.com/btc")  # ❌ Real API
```

### 7. Executar Testes Antes de Commitar
```bash
# Ativar environment
source .venv/bin/activate

# Rodar todos os testes
pytest -q

# Rodar com cobertura
pytest --cov=btc_trading_agent --cov-report=term -q

# Rodar testes específicos
pytest tests/test_models.py -v
pytest tests/test_api.py::test_health_check -v

# CI/CD (GitHub Actions)
pytest --cov-report=xml --junitxml=results.xml -q
```

### 8. Padrão de Nominação
```
✅ test_<funcao_testada>.py
✅ test_<modulo>.py
✅ def test_<descricao>():
✅ def test_<descricao>_<cenario>():

❌ test_functions.py (genérico)
❌ def test1():
❌ def testado():
```

---

## 🚨 Checklist Antes de Fazer Commit

```
Código novo? → Incluir testes? ← SIM obrigatório

☐ Código escrito
☐ Testes escritos (conftest + test_*.py)
☐ pytest -q passou 100%
☐ pytest --cov=... ≥ 80% cobertura
☐ Sem warnings/errors
☐ Código segue style guide (.pylintrc / black)
☐ Type hints completos
☐ Docstrings em PT-BR
☐ Pronto para git commit
```

---

## 📊 Exemplos de Cobertura

### Bom (90%+)
```
Name                       Stmts   Miss  Cover   Missing
─────────────────────────────────────────────────────
models.py                    50      2    96%     78, 92 (erro paths)
api.py                      100      8    92%     120-125 (fallback)
utils.py                     30      1    97%     45 (deprecated)
─────────────────────────────────────────────────────
TOTAL                       180      11   94%  ✅ ACEITÁVEL
```

### Ruim (<70%)
```
Name                       Stmts   Miss  Cover   Missing
─────────────────────────────────────────────────────
models.py                    60     30    50%     20-80 ❌
api.py                      100     45    55%     1-100 ❌
─────────────────────────────────────────────────────
TOTAL                       160     75    53%  ❌ REJEITÁVEL — reescrever testes
```

---

## 🔧 Setup Inicial

### 1. Instalar Dependências
```bash
pip install pytest pytest-cov pytest-mock pytest-asyncio
```

### 2. Criar conftest.py na Raiz
```python
# tests/conftest.py
import pytest
import logging

logging.basicConfig(level=logging.DEBUG)

@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment antes de cada teste."""
    import os
    os.environ.pop("DATABASE_URL", None)
    yield
```

### 3. Rodar Testes Pipeline
```bash
# No .github/workflows/test.yml
- name: Run tests with coverage
  run: |
    pytest --cov=btc_trading_agent \
           --cov=specialized_agents \
           --cov-report=xml \
           --junitxml=results.xml \
           -q
    
    # Fail if coverage < 80%
    coverage report --fail-under=80
```

---

## 🚫 O Que NÃO Fazer

```python
# ❌ Testes sem assert
def test_algo():
    resultado = fazer_algo()  # Nada acontece!

# ❌ Testes que usam dados reais
def test_price():
    price = requests.get("https://api.real.com").json()  # NÃO!

# ❌ Testes interdependentes
def test_a():
    global shared_state  # Nunca use global
    shared_state = 10

def test_b():
    assert shared_state == 10  # Falha se test_a não roda antes

# ❌ Testes lentos sem skip
def test_download_100mb():  # Deve levarte 2+ minutos!
    arquivo = baixar_arquivo_grande()  # Timeout no CI
    assert arquivo

# ✅ Correto: marcar slow
@pytest.mark.slow
def test_download_100mb():
    arquivo = baixar_arquivo_grande()
    assert arquivo

# Rodar: pytest -m "not slow" (pula testes lentos)
```

---

## 📈 Métricas Esperadas

| Projeto | Cobertura | Status |
|---------|-----------|--------|
| `btc_trading_agent` | 85%+ | ✅ OK |
| `specialized_agents` | 82%+ | ✅ OK |
| `tools/` | 75%+ | ⚠️ Aceitável |
| `scripts/` | 60%+ | ⚠️ Scripts são leves |

---

## 🎯 Resumo

**TODO código que entra no repositório DEVE ter testes.**

- ✅ Correção → escrever teste para o bug (prova que foi corrigido)
- ✅ Feature → escrever testes de comportamento esperado
- ✅ Refactor → manter testes existentes funcionando (100% pass rate)
- ❌ Commit sem testes → REJECTED pelo pre-commit hook ou CI

**Sem testes, o código não é confiável e não deve entrar em produção.**

---

**Documento**: .github/instructions/testing-mandatory.md  
**Versão**: 2026-03-07  
**Aplicável a**: Todo desenvolvedor, toda feature
