# 🧪 Treinamento do Agent de Testes

## Diretiva Principal

**TODAS AS VEZES QUE EXECUTAR, AUMENTE A COBERTURA DE TESTES ATÉ CHEGAR EM 100%**

### 🚨 REGRAS OBRIGATÓRIAS
1. **COMMIT IMEDIATO** - Sempre fazer commit após testes passarem com sucesso
2. **DEPLOY DIÁRIO** - No fim do dia, fazer deploy da versão estável no servidor

---

## Regras de Execução

### 1. Análise de Cobertura
Antes de cada execução, o agent deve:
```bash
# Verificar cobertura atual
pytest --cov=. --cov-report=term-missing --cov-report=html
```

### 2. Identificar Gaps
- Listar módulos com cobertura < 100%
- Priorizar arquivos críticos (api.py, agent_manager.py, etc.)
- Identificar funções/métodos sem testes

### 3. Gerar Testes Incrementalmente
Para cada execução:
1. Escolher o módulo com menor cobertura
2. Gerar testes para funções não cobertas
3. Executar e validar os novos testes
4. Repetir até atingir 100% no módulo
5. Mover para o próximo módulo

### 4. Padrão de Testes
```python
import pytest
from unittest.mock import Mock, patch, AsyncMock

class TestNomeDoModulo:
    """Testes para [modulo]"""
    
    def setup_method(self):
        """Setup antes de cada teste"""
        pass
    
    def test_funcao_caso_sucesso(self):
        """Testa [funcao] em caso de sucesso"""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_funcao_caso_erro(self):
        """Testa [funcao] em caso de erro"""
        pass
    
    @pytest.mark.asyncio
    async def test_funcao_async(self):
        """Testa função assíncrona"""
        pass
```

---

## Metas de Cobertura por Módulo

| Módulo | Meta | Prioridade |
|--------|------|------------|
| `specialized_agents/api.py` | 100% | 🔴 Alta |
| `specialized_agents/agent_manager.py` | 100% | 🔴 Alta |
| `specialized_agents/agent_communication_bus.py` | 100% | 🔴 Alta |
| `specialized_agents/language_agents.py` | 100% | 🟡 Média |
| `specialized_agents/rag_manager.py` | 100% | 🟡 Média |
| `specialized_agents/docker_orchestrator.py` | 100% | 🟡 Média |
| `dev_agent/agent.py` | 100% | 🟡 Média |
| `dev_agent/llm_client.py` | 100% | 🟡 Média |
| `dev_agent/test_runner.py` | 100% | 🟢 Baixa |

---

## Checklist de Cada Execução

- [ ] Executar `pytest --cov` para ver cobertura atual
- [ ] Identificar próximo módulo/função a cobrir
- [ ] Gerar testes usando padrão AAA (Arrange-Act-Assert)
- [ ] Executar novos testes
- [ ] Verificar se cobertura aumentou
- [ ] **🚨 OBRIGATÓRIO: Commitar imediatamente após testes passarem**
- [ ] Commitar com mensagem: `test: increase coverage for [module] to X%`
- [ ] Push para repositório remoto
- [ ] Reportar progresso no log
- [ ] **🚨 FIM DO DIA: Deploy da versão estável no servidor**

---

## Relatório de Progresso

O agent deve gerar um relatório após cada execução:

```
📊 RELATÓRIO DE COBERTURA
========================
Execução: [timestamp]
Cobertura Anterior: X%
Cobertura Atual: Y%
Delta: +Z%

Módulos Atualizados:
- [modulo1]: X% → Y%
- [modulo2]: X% → Y%

Próximos Alvos:
1. [modulo_com_menor_cobertura]
2. [segundo_modulo]

Estimativa para 100%: N execuções
```

---

## Comandos Úteis

```bash
# Cobertura geral
pytest --cov=specialized_agents --cov=dev_agent --cov-report=term-missing

# Cobertura de arquivo específico
pytest --cov=specialized_agents/api --cov-report=term-missing tests/test_api.py

# Gerar relatório HTML
pytest --cov=. --cov-report=html
# Abrir: htmlcov/index.html

# Testes com verbose
pytest -v --tb=short

# Apenas testes que falharam anteriormente
pytest --lf
```

---

## Integração com CI

Adicionar ao `.github/workflows/test.yml`:
```yaml
- name: Run tests with coverage
  run: |
    pytest --cov=. --cov-report=xml --cov-fail-under=80
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

---

*Este documento deve ser consultado pelo Agent de Testes antes de cada execução*
