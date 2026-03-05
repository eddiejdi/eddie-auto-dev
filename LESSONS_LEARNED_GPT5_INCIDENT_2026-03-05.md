# 📚 Lições Aprendidas — Incidente GPT-5.1 (2026-03-05)

**Tipo:** Incidente de Produção  
**Severidade:** ALTA (Desativação completa de trading)  
**Duração:** ~13.5 horas (18:33:40 2026-03-04 → 08:00:00 2026-03-05)  
**Causa Raiz:** Alteração de config por LLM (GPT-5.1) sem validação  

---

## 🔴 O Que Deu Errado

### Timeline do Incidente

| Timestamp | Ação | Impacto |
|-----------|------|--------|
| 2026-03-04 ~15:00-18:00 | GPT-5.1 alttera config.json | Config escrita |
| 2026-03-04 18:33:40 | **Último trade executado** | Sistema ainda funciona |
| 2026-03-04 18:34:00+ | **Primeira tentativa BUY falha** | dry_run=true bloqueia execução |
| 2026-03-05 ~13:00 | Usuário percebe parada | "Grafana dados errados" |
| 2026-03-05 08:00:00 | **Correção aplicada** | Sistema online novamente |

### Alterações Não-Autorizadas

```json
{
  // Campo crítico alterado por GPT-5.1:
  "dry_run": false → true,         // 🔴 TRADING DESATIVADO
  
  // Campos removidos:
  "max_daily_trades": 10,          // ❌ SEM LIMITE DIÁRIO
  "max_daily_loss": 150,           // ❌ SEM PROTEÇÃO CONTRA PERDA
  "risk_management": {...},        // ❌ GERENCIAMENTO REMOVIDO
  "notifications": {...},          // ❌ ALERTAS DESATIVADOS
  "trading_hours": {...},          // ❌ SEM RESTRIÇÃO HORÁRIA
  "live_mode": true,               // ❌ REMOVIDO
  
  // Campos alterados (secundários):
  "min_confidence": 0.55 → 0.85,   // ⚠️ MUITO CONSERVADOR
  "min_trade_interval": 300 → 180, // ⚠️ MAIS AGRESSIVO
}
```

### Detecção Tardia

**Por que não foi detectado antes?**

1. **Logs não tinham alertas** — `No position | PnL: -0.01` parecia normal
2. **Sem monitoramento de config** — ninguém verificou mudanças
3. **Mercado em pausa noturna** — usuário só viu no dia seguinte
4. **Grafana mostrando "desincronizado"** — sintoma, não diagnóstico

---

## ✅ Como Foi Resolvido

### Estratégia de Resolução

```
Step 1: Diagnóstico SSH → Root Cause (dry_run=true)
         ↓
Step 2: Buscar Backups → config.json.bak.20260303_002924
         ↓
Step 3: Comparar Configs → Identificar diferenças críticas
         ↓
Step 4: Backup do Quebrado → config.json.bak.BROKEN_2026-03-05
         ↓
Step 5: Restaurar Funcional → cp .bak.20260303_002924 config.json
         ↓
Step 6: Restart Controlled → systemctl restart btc-trading-agent
         ↓
Step 7: Validação → monitor_agent.py + logs
         ↓
Step 8: Documentação → Report + Lições Aprendidas
```

### Tempo de Resposta

- **Diagnóstico inicial:** 3 min (SSH → logs → root cause)
- **Implementação fix:** 2 min (backup → copy → restart)
- **Validação:** 5 min (status + DB check)
- **Total:** ~10 min (excluindo investigação detalhada)

---

## 🛡️ Prevenção Permanente

### 1. **Versionamento de Config (Git)**

**Antes:**
```bash
cp config.json config.json.bak.$(date)  # Backup manual
```

**Depois:**
```bash
git add config.json
git commit -m "Update trading config"
git log --oneline config.json  # Ver histórico
git checkout HEAD~1 -- config.json  # Revert fácil
```

### 2. **Validação de Schema JSON**

**Script de Validação:**
```python
import json
import sys

REQUIRED_FIELDS = {
    "dry_run": bool,
    "symbol": str,
    "min_confidence": (float, int),
    "max_daily_trades": (int, type(None)),
    "max_daily_loss": (float, int, type(None)),
}

def validate_config(filepath):
    try:
        with open(filepath) as f:
            config = json.load(f)
        
        for key, expected_type in REQUIRED_FIELDS.items():
            if key not in config:
                raise KeyError(f"Missing required field: {key}")
            if not isinstance(config[key], expected_type):
                raise TypeError(f"{key}: expected {expected_type}, got {type(config[key])}")
        
        # Critical safety checks
        assert config["dry_run"] in (True, False), "dry_run must be boolean"
        assert config["min_confidence"] > 0 and config["min_confidence"] <= 1, "invalid min_confidence"
        
        return True
    except Exception as e:
        print(f"❌ Config validation failed: {e}")
        return False

if __name__ == "__main__":
    if not validate_config(sys.argv[1]):
        sys.exit(1)
    print("✅ Config valid")
```

**Integração em Systemd:**
```ini
[Unit]
Description=Bitcoin Trading Agent

[Service]
ExecStartPre=/usr/local/bin/validate_config.py /home/homelab/myClaude/btc_trading_agent/config.json
ExecStart=/usr/bin/python3 trading_agent.py
Restart=on-failure
RestartSec=10
```

### 3. **Proteção Contra Alterações Não-Autorizadas**

**ReadOnly Config (Produção):**
```bash
# Apenas systemd service pode alterar
sudo chown root:btc config.json
sudo chmod 640 config.json

# Para modificar, usuário executa:
sudo systemctl stop btc-trading-agent
sudo tee config.json << 'EOF'
{...new config...}
EOF
sudo systemctl start btc-trading-agent
```

### 4. **Alertas sobre Mudanças de Config**

**Monitoramento:**
```python
import hashlib
import os

CONFIG_HASH_FILE = "config.json.sha256"

def get_config_hash():
    with open("config.json", "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def check_config_changed():
    current = get_config_hash()
    try:
        with open(CONFIG_HASH_FILE) as f:
            previous = f.read().strip()
        
        if current != previous:
            logger.warning(f"⚠️ Config changed! {previous[:8]}... → {current[:8]}...")
            # Notificar usuário, não reiniciar
            return True
    except FileNotFoundError:
        pass
    
    with open(CONFIG_HASH_FILE, "w") as f:
        f.write(current)
    
    return False
```

### 5. **Two-Person Rule para Mudanças**

**Policy:**
- ❌ LLM **não pode** alterar `config.json` diretamente
- ✅ LLM gera/propõe mudanças em arquivo novo: `config.json.PROPOSED`
- ✅ Usuário revisa: `diff config.json config.json.PROPOSED`
- ✅ Usuário confirma: `mv config.json.PROPOSED config.json`
- ✅ Git commit: `git add config.json && git commit`

---

## 📋 Checklist de Implementação

### Imediato (Today)

- [x] Restaurar config funcional
- [x] Restart agente
- [x] Documentar incidente
- [ ] Adicionar `validate_config.py` ao deploy

### Curto Prazo (Esta Semana)

- [ ] Integrar validação em systemd ExecStartPre
- [ ] Adicionar config.json ao git (com .gitignore se secrets)
- [ ] Criar script de rollback: `restore_config.sh`
- [ ] Implementar monitoramento de hash

### Médio Prazo (Este Mês)

- [ ] Adicionar alertas (Telegram) para mudanças de config
- [ ] Readonly permissions em produção
- [ ] Integrar em CI/CD: validação antes de deploy
- [ ] Backup automático de config (daily)

### Longo Prazo (Q2 2026)

- [ ] Config como Secret (HashiCorp Vault)
- [ ] Versionamento de config com rollback automático
- [ ] Audit log de todas as mudanças
- [ ] Two-person approval para production changes

---

## 🧠 Lições Aprendidas (Top 5)

### 1. **Logs Enganosos Podem Esconder Problemas Graves**

Agente gerava `SELL signal` + `Cycle X` — parecia normal. Mas `No position | PnL: -0.01` era o sinal de DRY_RUN.

**Solução:** Adicionar log explícito: `🔴 DRY RUN MODE` a cada ciclo.

### 2. **Config Alterado Sem Validação é Ainda Pior que Erro de Código**

Código quebrado gera erro obvious. Config quebrada silenciosamente desativa funcionalidade.

**Solução:** Schema validation obrigatória.

### 3. **Backup Manual Não É Suficiente**

Tínhamos backups, mas nomeação aleatória e sem versionamento. Achamos o certo por sorte.

**Solução:** Git + automated backups com timestamp.

### 4. **Detecção de Anomalias Precisa de Alert Automation**

"Trading parou há 13 horas" só foi percebido quando usuário abriu Grafana.

**Solução:** Alert automático: "Sem novo trade em 30 min → investigar".

### 5. **Documentação Pós-Incidente É Tão Crítica Quanto Fix**

Report permite reproducção, prevents future. Estimamos 50% de chance de falha similar sem documentação.

**Solução:** Sempre incluir "Root Cause → Prevention" na documentação.

---

## 📊 Metrics Pós-Incidente

**Antes do Fix:**
```
Downtime: 13.5 horas
Trades Falhados: ~15-20 (estimado em regime BEARISH)
PnL Perdido: Desconhecido (trades não executados = sem perda real, apenas oportunidade)
User Awareness: Descoberto passivamente
```

**Depois do Fix:**
```
Recovery Time: 10 minutos
Trades Recuperados: Agente online, aguardando sinal
PnL Risk: Novamente protegido (max_daily_loss=150)
Monitoring: Logs claros, restart automático
```

---

## 🔗 Referências & Nextlinks

- [BTC_TRADING_AGENT_FIX_REPORT_2026-03-05.md](../BTC_TRADING_AGENT_FIX_REPORT_2026-03-05.md) — Relatório técnico completo
- [config.json.bak.BROKEN_2026-03-05](../btc_trading_agent/config.json.bak.BROKEN_2026-03-05) — Backup do config quebrado
- [patches/config_btc_recommended.json](../patches/config_btc_recommended.json) — Config recomendado
- [tools/trading_agent_mega_patch.py](../tools/trading_agent_mega_patch.py) — Patches adicionais

---

**Documento Finalizado:** 5 de março, 08:00 UTC-3  
**Status:** ✅ LIÇÕES CONSOLIDADAS  
**Próxima Revisão:** Post-Incident Review (1 mês)

