# Deploy de drop-ins systemd — variáveis

Variáveis de `scripts/deploy_btc_trading_profiles.sh` e
`scripts/check_systemd_dropin_drift.py` que controlam a instalação dos drop-ins
`*.service.d/*.conf` no homelab (192.168.15.2).

Política, escopo e pendências: [`../systemd/DROPIN_DEPLOY_PARITY.md`](../systemd/DROPIN_DEPLOY_PARITY.md).

| Variável | Default | Propósito |
|---|---|---|
| `SYSTEMD_SYSTEM_DIR` | `/etc/systemd/system` | Diretório de units do host onde os drop-ins gerenciados são instalados. Sobrescrito só em teste (`tests/test_systemd_dropin_parity.py` aponta para um `/etc` falso em `tmp_path` para exercitar `sync_systemd_dropins` sem root). Em produção **não** mude. |
| `DROPIN_RESTART_STAGGER_SEC` | `3` | Intervalo entre restarts das units cujo drop-in mudou (`ollama.service`, `ollama-gpu1.service`). Mesma lógica de `AGENT_RESTART_STAGGER_SEC`: restart em rajada sobrecarrega o Secrets Agent e o Ollama. |

## Constantes relacionadas (não são env vars)

| Nome | Onde | Papel |
|---|---|---|
| `DROPIN_MANIFEST` | deploy | Caminho de `systemd/managed_dropins.conf`, a lista dos diretórios gerenciados. |
| `DROPIN_DRIFT_CHECKER` | deploy | Caminho de `scripts/check_systemd_dropin_drift.py`, chamado no hook de completude. |
| `MANAGED_TOOLS` | deploy | Scripts de `tools/` referenciados por `ExecStart=`/`ExecStartPost=` das units gerenciadas. Sincronizados **antes** dos drop-ins. |
| `DROPIN_RESTART_SKIP` | deploy | Units cujo restart já acontece em outro ponto do deploy. |
| `DROPIN_CHANGED_UNITS` | deploy | Preenchido por `sync_systemd_dropins()`, consumido por `restart_dropin_changed_units()`. |
