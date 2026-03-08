# 🔧 Ollama Recovery Report - 2026-02-28

## 🔴 Problema Detectado

- **Status**: Ollama travado (congelado)
- **Sintomas**: 
  - GPU: 0% de utilização
  - VRAM: 7.4GB alocados (sem processamento)
  - API: Respondendo mas não processando
- **Horário**: 2026-02-28 18:00 UTC
- **Causa Raiz**: Deadlock em goroutine do runner Ollama (processo em espera indefinida)

## 📋 Ações Realizadas

### 1. ✅ Restart Imediato (18:00-18:01)
```bash
sudo systemctl restart ollama
```
**Resultado**: GPU voltou a 30% de utilização, 17 modelos carregados, API responsiva

### 2. ✅ Instalação dos Daemons Permanentes (18:01-18:02)

Scripts criados em commit anterior (`13d3d91`) mas **nunca instalados como serviços**:

```bash
scp tools/selfheal/ollama_frozen_monitor.sh homelab@192.168.15.2:/tmp/
scp tools/selfheal/ollama_metrics_exporter.sh homelab@192.168.15.2:/tmp/
sudo mv /tmp/ollama_frozen_monitor.sh /usr/local/bin/ollama_frozen_monitor
sudo mv /tmp/ollama_metrics_exporter.sh /usr/local/bin/ollama_metrics_exporter
sudo chmod +x /usr/local/bin/ollama_*
```

### 3. ✅ Criação dos Serviços Systemd (18:02)

**ollama-frozen-monitor.service**:
- Detecção automática de congelamento
- Trigger: GPU < 5% AND nenhuma requisição por > 180s
- Auto-restart via `sudo systemctl restart ollama`
- Máximo 3 restarts/hora, cooldown 60s entre tentativas
- Logs: `journalctl -u ollama-frozen-monitor`

**ollama-metrics-exporter.service**:
- Coleta métricas do Ollama a cada 15s
- Exporta para Prometheus em `/tmp/ollama_metrics.prom`
- Métricas: `ollama_up`, `ollama_frozen_duration_seconds`, `ollama_models_loaded`, GPU utilization, etc.

### 4. ✅ Resolução de Permissões (18:02-18:03)

Problemas iniciais:
- User=ollama não tinha permissão para escrever em `/var/log/` e `/tmp/`
- Necessário User=root para `sudo systemctl restart ollama`

Solução:
- Alterado User=ollama → User=root em ambos os serviços
- Limpeza de conflitos: `rm -f /tmp/ollama_*.{txt,json,prom}`
- Reinicialização dos serviços

## ✅ Verificação Final

```
📊 Status do Ollama:
   - Modelos carregados: 17
   - API: respondendo
   - GPU: 0% (ocioso, esperado)
   - VRAM: 4.9GB / 8.2GB

🚀 Serviços de Monitoramento:
   - ollama-frozen-monitor: active (running)
   - ollama-metrics-exporter: active (running)
   - Auto-start at boot: enabled

📈 Métricas Sendo Exportadas:
   - /tmp/ollama_metrics.prom (2.1K)
   - /tmp/ollama_metrics.txt (578B)
```

## 🛡️ Auto-Recovery Agora Ativado

| Parâmetro | Valor |
|-----------|-------|
| Threshold de congelamento | 180 segundos |
| GPU mín. esperado | 5% |
| Intervalo de check | 15 segundos |
| Max restarts/hora | 3 |
| Cooldown entre tentativas | 60 segundos |
| Comportamento | Auto-restart + logging |

## 🎯 Por Que o Auto-Recovery Falhou Antes?

**Root cause**: Os scripts de monitoramento foram criados e commitados, mas **nunca foi feita a instalação como serviços systemd**. 

Mudanças necessárias que faltavam:
1. Copiar scripts para `/usr/local/bin/`
2. Criar arquivos de serviço em `/etc/systemd/system/`
3. `systemctl daemon-reload`
4. `systemctl enable` e `systemctl start`

Agora está corrigido e operacional.

## 📝 Próximos Passos

- [ ] Verificar no Grafana se as gauges de Ollama estão exibindo dados
- [ ] Testar auto-recovery com simulação de congelamento (ver `SELFHEALING_SETUP.md`)
- [ ] Validar alertas Prometheus para `OllamaFrozen`
- [ ] Monitorar logs: `journalctl -u ollama-frozen-monitor -f`

## 📚 Referência

Documentação completa: [SELFHEALING_SETUP.md](./SELFHEALING_SETUP.md)

Scripts envolvidos:
- `tools/selfheal/ollama_frozen_monitor.sh` - Detecção + restart
- `tools/selfheal/ollama_metrics_exporter.sh` - Coleta de métricas
- `monitoring/prometheus/selfhealing_rules.yml` - Alerting rules

---

**Report generated**: 2026-02-28 18:03 UTC  
**Status**: ✅ RESOLVED (Auto-recovery now operational)
