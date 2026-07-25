# Drop-ins systemd — paridade repo ↔ homelab

## O buraco que isto fecha

Até 2026-07-25 o `scripts/deploy_btc_trading_profiles.sh` instalava apenas os
arquivos de `MANAGED_SYSTEMD_UNITS` (units inteiras). **Nenhum diretório
`*.service.d/` era copiado.** Consequências:

1. Corrigir um `.conf` no git não mudava nada em produção.
2. Pior: `systemd/**/*.service.d/**` nem estava nos `paths` do gatilho do
   workflow — mudar um drop-in **não disparava o deploy**.
3. Só `tools/ollama_gpu_coordinator.py` era sincronizado; `ollama_warmup.py`,
   `ollama_gpu_selfheal.py` e `ollama_offloader.py` não. Um drop-in que chama
   `ollama_warmup.py` num host sem esse arquivo perde o `ExecStartPost`.

Caso concreto: o PR #246 corrigiu
`crypto-agent@BTC_USDT_aggressive.service.d/zz-direct-ollama.conf`, que fixava
`OLLAMA_PLAN_MODEL=gemma3-fast:gpu1` — modelo que não está na GPU1 desde
2026-07-10 (é `lfm2.5-fast:gpu1`). Apontar para modelo não residente, com
`OLLAMA_MAX_LOADED_MODELS=1`, devolve 503 *"maximum pending requests exceeded"*
(mesma classe do #245). O PR consertou o repo; produção seguiu errada.

## Como funciona agora

| Peça | Papel |
|---|---|
| `systemd/managed_dropins.conf` | Manifesto: quais diretórios `*.service.d` o deploy instala. Fonte única. |
| `sync_systemd_dropins()` (deploy) | Copia `*.conf` para `/etc/systemd/system/` de forma **aditiva**, com backup do arquivo anterior. |
| `restart_dropin_changed_units()` | Restart escalonado **só** das units cujo `.conf` mudou e que não são reiniciadas em outro ponto do deploy. |
| `verify_systemd_dropin_parity()` | Hook de completude: falha o deploy se algum `.conf` versionado não chegou ao host. |
| `scripts/check_systemd_dropin_drift.py` | Verificador standalone (repo↔host), usado no deploy, no CI e no job agendado. |
| `.github/workflows/systemd-dropin-drift-check.yml` | Detecta drift **fora** de um deploy (edição manual no host) e alerta no Telegram. |
| `scripts/export_host_systemd_dropins.sh` | Traz para o git os `.conf` que só existem no host. |

### Ordem no deploy

```
sync_trading_runtime      # tools/*.py → /apps/crypto-trader/tools/  (ANTES dos drop-ins)
install_managed_units     # units inteiras
sync_systemd_dropins      # drop-ins
daemon-reload
restart_dropin_changed_units   # ollama.service / ollama-gpu1.service, se mudaram
restart ollama-gpu-coordinator
restart escalonado dos crypto-agent@*
verify_systemd_dropin_parity   # falha se sobrou divergência
```

As tools vão **antes** dos drop-ins de propósito: um `ExecStartPost=` apontando
para script inexistente derruba o start da unit.

## Regras que o instalador respeita

### 1. Cópia aditiva — nunca `rsync --delete`

O host tem drop-ins vivos que **não estão no git**. Apagá-los quebraria
produção. Exemplos conhecidos:

| Arquivo | Onde | Por que importa |
|---|---|---|
| `ollama.service.d/zz-perf-containment.conf` | GPU0 | É o drop-in que **vence** por ordem alfabética em `OLLAMA_NUM_PARALLEL`/`OLLAMA_MAX_QUEUE` — ajustado no incidente 503-storm de 2026-07-24. Documentado em [`../variables-taxonomy/OLLAMA_PERF_CONTAINMENT.md`](../variables-taxonomy/OLLAMA_PERF_CONTAINMENT.md). |
| `ollama-gpu1.service.d/zz-gpu1-visible-device.conf` | GPU1 | Fixa a GPU visível da segunda instância. |
| `crypto-agent@*.service.d/zz-trading-preload.conf` | agents | Preload de modelo por perfil. |

O deploy **preserva** esses arquivos e os lista como `host_only` a cada
execução. O verificador também os reporta (sem contar como drift, a menos que
se passe `--fail-on-host-only`).

### 2. Templates com placeholder não são instalados

`crypto-agent@.service.d/common.conf` traz
`SECRETS_AGENT_API_KEY=<from_bitwarden>` e `TELEGRAM_BOT_TOKEN=<from_bitwarden>`.
Instalá-lo **apagaria as credenciais vivas** do crypto-agent. Arquivos que
casam com os padrões de redação (`<from_bitwarden>`, `<your_*>`, `CHANGEME`,
`REPLACE_ME`, `<REDACTED>`, `<PLACEHOLDER>`) são pulados no install e marcados
`redacted` no verificador — divergência neles é esperada, não drift.

Os `OLLAMA_*_HOST` do `common.conf` do host continuam sendo mantidos pelo
`sed -i` já existente no deploy (todos para o coordenador `:11437`). Por isso os
valores no template versionado (11434/11435) divergem do runtime **de
propósito**.

### 3. Restart mínimo

- `crypto-agent@*` (template e instâncias): já cobertos pelo restart escalonado
  de `AGENT_SERVICES` — não reiniciam duas vezes.
- `ollama-gpu-coordinator.service`: restart incondicional já existente.
- `ollama.service` / `ollama-gpu1.service`: reiniciam **só** se o `.conf` mudou,
  escalonados (`DROPIN_RESTART_STAGGER_SEC`, default 3s), antes do coordenador
  e dos agents, com espera de readiness em `/api/tags`.

## Escopo — o que está fora e por quê

O manifesto cobre só a pilha trading/Ollama do homelab (192.168.15.2). Ficam de
fora, deliberadamente:

| Diretório | Motivo |
|---|---|
| `ltfs-lto6.service.d`, `ltfs-cache-flush.service.d`, `lto6-drain-backups.service.d`, `nextcloud-tape-backup.*.d`, `nvme-tape-drain.*.d` | Rodam na **NAS** (192.168.15.4), não no homelab. Ver `feedback_nas_homelab_separation`. |
| `wg-quick@protonvpn.service.d`, `cloudflared-rpa4all.service.d` | Rede/túnel — mudança exige janela própria, não pode entrar de carona num deploy de trading. |
| `akash-sweep.service.d` | Contém segredo (`secrets.conf` com placeholder) e pertence a outro pipeline. |
| `coordinator-agent.service.d` | Outro serviço, outro deploy. |
| `systemd/*.conf` soltos (`ollama-optimized.conf`, `ollama-gpu-boot-order.conf`, `btc-trading-agent-validate.conf`, `nginx-dns-over-tls.conf`, `pihole-ipv6-dns-fix.override.conf`, `radvd.conf`) | Não estão numa árvore `<unit>.d/`; o destino no host é ambíguo. Instalar no lugar errado é pior que não instalar. |

Para trazer um diretório para o escopo, basta acrescentá-lo a
`systemd/managed_dropins.conf` — o deploy, o gatilho do workflow e os testes
leem o mesmo arquivo.

## Operação

Checar divergência (no homelab):

```bash
python3 scripts/check_systemd_dropin_drift.py --strict --verbose
```

Versionar o que só existe no host:

```bash
scripts/export_host_systemd_dropins.sh --apply
```

> Revise segredo por segredo antes de `git add`. Arquivo com credencial real
> **não** vai para o git: mantenha o template com `<from_bitwarden>` e registre
> a exceção nesta página.

Verificação manual do caso do PR #246:

```bash
sudo grep -r OLLAMA_PLAN_MODEL /etc/systemd/system/crypto-agent@BTC_USDT_aggressive.service.d/
```

```bash
sudo systemctl show crypto-agent@BTC_USDT_aggressive -p Environment | tr ' ' '\n' | grep OLLAMA_PLAN
```

Ambos precisam mostrar `lfm2.5-fast:gpu1` — o segundo confirma que o drop-in
venceu o `EnvironmentFile=/etc/crypto-agent/models.env`.

## Pendência conhecida

Os três drop-ins host-only da tabela acima **ainda não estão versionados**: a
LAN 192.168.15.x está inacessível (enp0s31f6 em NO-CARRIER) e não foi possível
lê-los. O caminho é rodar `scripts/export_host_systemd_dropins.sh --apply` no
homelab (direto ou via runner self-hosted `homelab`) e commitar o resultado.
Até lá vale o risco descrito em `feedback_git_not_enough`: `ExecStart=` fora do
git é irrecuperável.
