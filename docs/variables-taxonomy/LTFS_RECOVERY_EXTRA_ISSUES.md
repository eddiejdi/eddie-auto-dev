# LTFS Recovery / Validação — Variáveis

Serviço: `ltfs_recovery.py` (orchestrator, NAS), `validate_nextcloud_flow.sh`.

| Variável | Default | Propósito |
|---|---|---|
| `LTFS_KNOWN_ISSUES_EXTRA_FILE` | `/etc/ltfs-recovery/known_issues.extra.json` | Arquivo JSON (lista) com padrões de falha LTFS extras, versionado fora do código (G18). Adiciona issues ou substitui uma embutida (mesmo `id` vence a embutida). Re-lido a cada detecção — novo padrão de incidente não exige deploy. |
| `VALIDATION_MAX_RESULTS` | `10` | Número máximo de `nextcloud_flow_validation_results.txt*` retidos pela rotação no `tests/validate_nextcloud_flow.sh` (G20). |

## Consumidor: `ltfs_recovery.py`

O orchestrator lê o arquivo de issues extras apenas se existir; falha de leitura
não derruba a detecção base (log WARN e segue com `KNOWN_ISSUES` embutido).
