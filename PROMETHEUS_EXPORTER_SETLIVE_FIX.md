# Correção do Endpoint /set-live - Prometheus Exporter BTC

**Data**: 27 de fevereiro de 2026  
**Problema**: O endpoint `http://192.168.15.2:9092/set-live` não persistia configurações corretamente entre moedas  
**Raiz do Problema**: Todas as 6 instâncias de prometheus_exporter.py compartilhavam o mesmo arquivo `config.json`

---

## Diagnóstico

### Arquitetura Atual
```
6 Instâncias de prometheus_exporter.py (portas 9092-9097)
├── BTC (9092) → config.json (HARDCODED)
├── ETH (9098) → config.json (HARDCODED) ❌ WRONG!
├── XRP (9094) → config.json (HARDCODED) ❌ WRONG!
├── SOL (9095) → config.json (HARDCODED) ❌ WRONG!
├── DOGE (9096) → config.json (HARDCODED) ❌ WRONG!
└── ADA (9097) → config.json (HARDCODED) ❌ WRONG!
```

### Código Problemático
**Linha 31 do prometheus_exporter.py** (ANTES):
```python
CONFIG_PATH = BASE_DIR / "config.json"  # Hardcoded - viola isolamento
```

**Função main() (linha ~1016)** (ANTES):
```python
def main():
    port = int(os.environ.get("METRICS_PORT", "9092"))
    
    # Load symbol from config
    config_name = os.environ.get("COIN_CONFIG_FILE", "config.json")  # ← Sistema simétrico
    config_path = BASE_DIR / config_name
    _symbol = "BTC-USDT"
    try:
        with open(config_path) as _f:
            _cfg = json.load(_f)
            _symbol = _cfg.get("symbol", "BTC-USDT")
    except Exception:
        pass
    os.environ.setdefault("COIN_SYMBOL", _symbol)
```

**Problema**: `main()` lê de `config_{COIN}.json` para descobrir o símbolo,  
mas quando `/set-live` é chamado, ele escreve em `config.json` global (linha 54)`

---

## Solução Implementada

### Mudança 1: Remover CONFIG_PATH Global
**ANTES** (linha 31):
```python
CONFIG_PATH = BASE_DIR / "config.json"
```

**DEPOIS**: Remover esta linha completament

e

### Mudança 2: Criar Função Dinâmica
**Adicionar após linha ~30** (após `SCHEMA = "btc"`):
```python
def get_config_path():
    """Obtém o caminho do arquivo de config específico da moeda"""
    config_name = os.environ.get("COIN_CONFIG_FILE", "config.json")
    return BASE_DIR / config_name
```

### Mudança 3: Substituir Todas as Referências
Substituir `CONFIG_PATH` por `get_config_path()` em:
- Linha 37: `load_config()` → `with open(get_config_path())`
- Linha 51: `save_config()` → `dir=os.path.dirname(get_config_path())`
- Linha 54: `save_config()` → `os.replace(tmp_path, get_config_path())`

---

## Resultado Esperado (APÓS FIX)

```
6 Instâncias de prometheus_exporter.py (portas 9092-9097)
├── BTC (9092) → COIN_CONFIG_FILE=config.json → /set-live modifica config.json ✅
├── ETH (9098) → COIN_CONFIG_FILE=config_ETH_USDT.json → /set-live modifica config_ETH_USDT.json ✅
├── XRP (9094) → COIN_CONFIG_FILE=config_XRP_USDT.json → /set-live modifica config_XRP_USDT.json ✅
├── SOL (9095) → COIN_CONFIG_FILE=config_SOL_USDT.json → /set-live modifica config_SOL_USDT.json ✅
├── DOGE (9096) → COIN_CONFIG_FILE=config_DOGE_USDT.json → /set-live modifica config_DOGE_USDT.json ✅
└── ADA (9097) → COIN_CONFIG_FILE=config_ADA_USDT.json → /set-live modifica config_ADA_USDT.json ✅
```

### Logs do Exporter APÓS FIX
```
📁 Config:   /home/homelab/myClaude/btc_trading_agent/config_ETH_USDT.json  ← Específico
🪙 Symbol:   ETH-USDT                                                       ← Correto
```

---

## Como Aplicar a Correção

### Opção 1: Manual (Recommended)
```bash
cd /home/homelab/myClaude/btc_trading_agent

# Fazer backup
cp prometheus_exporter.py prometheus_exporter.py.bak

# Usar um editor para:
# 1. Remover linha 31: CONFIG_PATH = BASE_DIR / "config.json"
# 2. Após linha 30, adicionar a função get_config_path()
# 3. Substituir CONFIG_PATH por get_config_path() em 3 locais
```

### Opção 2: Script Python
```python
import re

filepath = "/home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py"
with open(filepath, "r") as f:
    lines = f.readlines()

# 1. Remover CONFIG_PATH
new_lines = [line for line in lines 
             if 'CONFIG_PATH = BASE_DIR / "config.json"' not in line]

# 2. Inserir função após SCHEMA = "btc"
output_lines = []
for i, line in enumerate(new_lines):
    output_lines.append(line)
    if 'SCHEMA = "btc"' in line:
        output_lines.append('\ndef get_config_path():\n')
        output_lines.append('    """Obtém o caminho do arquivo de config específico da moeda"""\n')
        output_lines.append('    config_name = os.environ.get("COIN_CONFIG_FILE", "config.json")\n')
        output_lines.append('    return BASE_DIR / config_name\n')

# 3. Substituir CONFIG_PATH
result = ''.join(output_lines).replace('CONFIG_PATH', 'get_config_path()')

with open(filepath, "w") as f:
    f.write(result)
```

### Após a Alteração: Reiniciar Serviços
```bash
sudo systemctl restart crypto-exporter@ADA_USDT.service \
                        crypto-exporter@DOGE_USDT.service \
                        crypto-exporter@ETH_USDT.service \
                        crypto-exporter@SOL_USDT.service \
                        crypto-exporter@XRP_USDT.service \
                        autocoinbot-exporter.service
```

---

## Testes de Validação

### Teste 1: Verificar que cada exporter usa seu config
```bash
# BTC (9092)
curl http://192.168.15.2:9092/set-dry     # def set dry run
curl http://192.168.15.2:9092/mode        # {"live_mode": false}

# ETH (9098) - independent config
curl http://192.168.15.2:9098/set-live    # set live
curl http://192.168.15.2:9098/mode        # {"live_mode": true}

# BTC should still be dry (not affected by ETH change)
curl http://192.168.15.2:9092/mode        # {"live_mode": false} ✅
```

### Teste 2: Confirmar que files foram modificados
```bash
grep "dry_run.*false" config_BTC_USDT.json       # BTC em dry run
grep "dry_run.*false" config_ETH_USDT.json       # ETH em live mode
# Devem ser diferentes se feita mudança separada em cada uma
```

---

## Arquivo afetado

**Path completo**: `/home/home lab/myClaude/btc_trading_agent/prometheus_exporter.py`

**Linhas a modificar**: 31, 37, 51-54, +32-36 (nova função)

**Arquivo de configuração de systemd**: `/etc/systemd/system/crypto-exporter@.service`
- Já contém: `Environment=COIN_CONFIG_FILE=config_%I.json` ✅ Correto

---

##  Regra do Projeto Violada

Conforme instruções em `.github/copilot-instructions.md`:
> **Regra obrigatória**: Cada exporter usa seu próprio `CONFIG_PATH` via `global CONFIG_PATH` em `main()`.

O código violava isso porque `CONFIG_PATH` era global e hardcoded, **ignorando** `COIN_CONFIG_FILE`.

---

## Resumo

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Isolamento de config | ❌ Todas compartilham config.json | ✅ Cada uma seu config_COIN.json |
| Persistência | ❌ /set-live em uma moeda afeta todas | ✅ Isolado por moeda |
| Logs do exporter | ❌ `config.json` | ✅ `config_ETH_USDT.json` |
| Cumprimento regra | ❌ CONFIG_PATH global | ✅ get_config_path() dinâmica |

---

## Observação Importante

A função `load_config()` e `save_config()` do arquivo são chamadas por:
- `/mode` - lê config
- `/set-live` -modifica config
- `/set-dry` - modifica config
- `/config` endpoint - lê config
- `/toggle-mode` - modifica config

Todas essas operações agora usarão o config isolado da moeda.

