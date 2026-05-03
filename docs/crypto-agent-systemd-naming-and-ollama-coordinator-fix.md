---
title: Correção: Naming systemd do crypto-agent & Ollama coordinator
date: 2026-05-03
---

# Resumo

Este documento descreve a correção aplicada no homelab para resolver dois problemas que deixavam os agentes de trading (crypto-agent) inoperantes e os modelos "shadowed" no Grafana:

- Instâncias `crypto-agent` duplicadas com nomes contendo hífen, que geravam paths errados para os envfiles.
- Arquivo `common.conf` com porta errada (11434) em vez do GPU coordinator (11437).

As ações abaixo foram executadas no homelab (192.168.15.2) e validadas com reinício do coordinator e dos agentes.

# Escopo

- Produtos afetados: agentes de trading (`crypto-agent@*`), painel Grafana (indicadores de modelo), Ollama GPU coordinator.
- Local das intervenções: `/etc/systemd/system/crypto-agent@.service*` e `/apps/crypto-trader/envfiles/` no homelab.

# Causa raiz

1. Systemd instances com hifen (`BTC-USDT-conservative`) foram iniciadas em paralelo às corretas com underscore (`BTC_USDT_conservative`). O uso de `%I` no unit template resulta em decoding que transforma hifens em barras, levando a path inválido para `EnvironmentFile`.
2. `common.conf` foi alterado inadvertidamente trocando a porta do GPU coordinator (`11437`) por uma das GPUs diretas (`11434`), provocando conexões diretas erradas e `ollama=shadow` nos agentes.

# Alterações aplicadas

- Parar e desabilitar instâncias com hífen:

```bash
sudo systemctl stop crypto-agent@BTC-USDT-conservative.service || true
sudo systemctl disable crypto-agent@BTC-USDT-conservative.service || true
sudo systemctl stop crypto-agent@BTC-USDT-aggressive.service || true
sudo systemctl disable crypto-agent@BTC-USDT-aggressive.service || true
```

- Corrigir template systemd para usar `%i` quando necessário e evitar usar `%I` em `EnvironmentFile`:

Arquivo afetado (homelab): `/etc/systemd/system/crypto-agent@.service`

Alteração recomendada:

```diff
- EnvironmentFile=-/apps/crypto-trader/envfiles/%I.env
+ EnvironmentFile=-/apps/crypto-trader/envfiles/%i.env
```

- Reverter porta do coordinator em `common.conf`:

```bash
sudo sed -i 's/11434/11437/g' /etc/systemd/system/crypto-agent@.service.d/common.conf
```

- Criar symlinks para compatibilidade (opcional, aplicado por segurança):

```bash
sudo ln -sf /apps/crypto-trader/envfiles/BTC_USDT_conservative.env /apps/crypto-trader/envfiles/BTC-USDT-conservative.env
sudo ln -sf /apps/crypto-trader/envfiles/BTC_USDT_aggressive.env /apps/crypto-trader/envfiles/BTC-USDT-aggressive.env
```

- Reiniciar systemd e serviços relevantes:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama-gpu-coordinator.service
sudo systemctl restart crypto-agent@BTC_USDT_conservative.service
sudo systemctl restart crypto-agent@BTC_USDT_aggressive.service
```

# Comandos de verificação usados

- Verificar status do coordinator e modelos:

```bash
sudo systemctl status ollama-gpu-coordinator.service -n 50
curl -s http://127.0.0.1:11437/models | jq '.'
```

- Verificar logs e bootstrap dos agents:

```bash
sudo journalctl -u crypto-agent@BTC_USDT_conservative.service -n 200 --no-tail
sudo journalctl -u crypto-agent@BTC_USDT_aggressive.service -n 200 --no-tail
```

- Verificar métricas no Grafana/Prometheus (exemplo):

```bash
curl -s 'http://localhost:9090/api/v1/query?query=crypto_agent_cycle_count' | jq '.data'
```

# Resultados e status

- Coordinator (`:11437`) respondendo e listando ~12 modelos.
- `crypto-agent@BTC_USDT_conservative`: ativo e com bootstrap completo (posições restauradas).
- `crypto-agent@BTC_USDT_aggressive`: ativo e processando SELLs.

# Arquivos modificados (homelab)

- `/etc/systemd/system/crypto-agent@.service` — `%I` → `%i` (EnvironmentFile)
- `/etc/systemd/system/crypto-agent@.service.d/common.conf` — porta revertida para 11437
- Symlinks em `/apps/crypto-trader/envfiles/` criados para compatibilidade

# Observações / Follow-ups

- Existem conflitos de merge não resolvidos em `specialized_agents/api.py` e `specialized_agents/user_management.py` no homelab; eles não bloqueiam o trading, mas devem ser resolvidos manualmente no repositório localizado em `/home/homelab/myClaude`.
- Recomenda-se padronizar nomenclatura para instâncias e documentar esse padrão (underscore obrigatório) no README operacional.

# Referências

- Memória interna: `/memories/repo/crypto-agent-systemd-naming.md`
- Commit relacionado: `f7d13842` (fix/trading: corrigir posições presas — ver histórico Git)

# Autor

Documentado automaticamente por agente durante sessão de troubleshooting (2026-05-03).
