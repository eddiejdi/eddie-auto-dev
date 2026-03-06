---
applyTo: "**/*test*,**/conftest*,**/*spec*,**/pytest*"
---

# Regras de Testes — Eddie Auto-Dev

## Execução
- `pytest -q` — executa testes unitários
- `-m integration` — testes que requerem serviços locais (API em 8503)
- `-m external` — testes com libs externas (chromadb, paramiko, playwright)
- Top-level tests ignorados por default; `RUN_ALL_TESTS=1` para incluir

## Markers (definidos em conftest.py)
```py
@pytest.mark.integration  # Requer API rodando
@pytest.mark.external     # Requer libs externas
```

## Convenções
- Funções async: usar `@pytest.mark.asyncio`
- DB: usar PostgreSQL (porta 5433, schema btc), nunca SQLite
- Cleanup: respeitar políticas de backup/container
- Secrets: nunca em testes, usar mocks ou vault
