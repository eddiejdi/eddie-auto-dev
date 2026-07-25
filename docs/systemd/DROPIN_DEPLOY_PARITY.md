## Estado da paridade (2026-07-25)

Após a captura e a reconciliação, `check_systemd_dropin_drift.py` contra o host:

```
Σ ok=13 missing=0 differs=0 redacted=0 not_synced=27 host_only=0
```

**Paridade total** nos arquivos sincronizáveis, e nada mais existindo só no
host. Os 27 `not_synced` são os drop-ins capturados que ainda não entraram na
allowlist — já idênticos ao host, versionados para não se perderem; entram um a
um quando houver mudança a empurrar.

Três arquivos onde o **host estava à frente** foram reconciliados trazendo a
versão viva para o repo:

| Arquivo | O que o repo não tinha |
|---|---|
| `ollama-gpu-coordinator.service.d/zz-dual-gpu-routing.conf` | `OLLAMA_NAS_HOST` e `GPU_COORD_POLL_INTERVAL_SEC` |
| `ollama.service.d/zzzz-warmup-curl.conf` | `OLLAMA_MAX_LOADED_MODELS` |
| `crypto-agent@.service.d/ollama-timeout.conf` | comentário ainda citava `gemma3-fast` |

Fora da allowlist e sem previsão de entrar: `crypto-agent@.service.d/cpuaffinity.conf`
(`CPUAffinity=2-15`), que não existe no host e seria inerte — `zz-proxy-protect.conf`
vem depois na ordem alfabética e reseta para `14-15`, o valor efetivo hoje.

Nota: `OLLAMA_NAS_HOST=http://192.168.15.4:11436` está configurado no
coordenador mas **não responde** (`curl` → `000`). Backend morto, a limpar em
mudança própria.

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

Caso concreto — e o desfecho é a moral da história. O PR #246 corrigiu
`crypto-agent@BTC_USDT_aggressive.service.d/zz-direct-ollama.conf`, que fixava
`OLLAMA_PLAN_MODEL=gemma3-fast:gpu1`, trocando por `lfm2.5-fast:gpu1`. Sem
acesso à LAN, presumiu-se que o comentário versionado ("plano vai para a GPU1")
refletia a decisão vigente. **Não refletia**: produção e
`deploy/crypto-agent/models.env` diziam `trading-analyst`. O #247 reverteu.

Ou seja, o problema nunca foi só "o repo não chega ao host" — era **não haver
como comparar os dois**. Sem comparação, o palpite sobre o que produção estava
rodando errou duas vezes seguidas.

## Como funciona agora

| Peça | Papel |
|---|---|
| `deploy/systemd-dropins-sync.allowlist` | **Fonte única** (criada no PR #248): opt-in **por arquivo** do que o deploy instala. O escopo de *observação* são os diretórios que ela toca. |
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

O host tem drop-ins vivos que **não estavam no git**. Apagá-los quebraria
produção. O deploy **preserva** esses arquivos e os lista como `host_only` a
cada execução; o verificador também os reporta (sem contar como drift, a menos
que se passe `--fail-on-host-only`).

**Inventário capturado em 2026-07-25** (via `rsync` do host, LAN pelo WiFi):
25 arquivos existiam só no homelab e agora estão versionados — 14 em
`ollama.service.d`, 5 em `ollama-gpu1.service.d`, 3 em
`ollama-gpu-coordinator.service.d`, 2 em `crypto-agent@.service.d`, 1 em
`crypto-agent@BTC_USDT_aggressive.service.d`. Nenhum continha credencial.

Dois deles eram, na verdade, arquivos soltos do repo instalados sob **outro
nome**, o que escondia a relação:

| No host | Origem no repo |
|---|---|
| `crypto-agent@.service.d/validate.conf` | `systemd/btc-trading-agent-validate.conf` |
| `ollama.service.d/gpu-boot-order.conf` | `systemd/ollama-gpu-boot-order.conf` |

E `ollama.service.d/ollama-optimized.conf` (host) divergia bastante do
`systemd/ollama-optimized.conf` (repo) — o do repo descreve uma RTX 3060 12GB e
`CPUAffinity=3-15`; o vivo diz RTX 2060 SUPER 8GB e `CPUAffinity=6,7`. As cópias
soltas na raiz de `systemd/` são **snapshots velhos**; a verdade é a que está em
`systemd/ollama.service.d/`.

### Cuidado com a ordem alfabética

O valor efetivo de cada variável é o do **último** drop-in em ordem
lexicográfica que a define. No `ollama.service` e no `ollama-gpu1.service`,
`zzzzz-idle-power-final.conf` (host-only, agora versionado) faz:

```
Environment=OLLAMA_KEEP_ALIVE=10m
Environment=OLLAMA_MAX_LOADED_MODELS=1
ExecStartPost=
```

Ou seja: **zera todo `ExecStartPost=`**. Consequência prática — o warmup
corrigido no PR #246 (`zzzz-warmup-curl.conf`) **nunca roda em produção**, e o
`OLLAMA_MAX_LOADED_MODELS=3` do `zzzz-warmup-curl.conf` do host é sobrescrito
para `1`. Confirmado no host:

```
$ systemctl show ollama.service -p ExecStartPost --value
(vazio)
```

Antes de concluir que um drop-in "consertou" algo, confirme com
`systemctl show <unit> -p Environment` / `-p ExecStartPost`.

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

A allowlist cobre só a pilha trading/Ollama do homelab (192.168.15.2). Ficam de
fora, deliberadamente:

| Diretório | Motivo |
|---|---|
| `ltfs-lto6.service.d`, `ltfs-cache-flush.service.d`, `lto6-drain-backups.service.d`, `nextcloud-tape-backup.*.d`, `nvme-tape-drain.*.d` | Rodam na **NAS** (192.168.15.4), não no homelab. Ver `feedback_nas_homelab_separation`. |
| `wg-quick@protonvpn.service.d`, `cloudflared-rpa4all.service.d` | Rede/túnel — mudança exige janela própria, não pode entrar de carona num deploy de trading. |
| `akash-sweep.service.d` | Contém segredo (`secrets.conf` com placeholder) e pertence a outro pipeline. |
| `coordinator-agent.service.d` | Outro serviço, outro deploy. |
| `systemd/*.conf` soltos (`ollama-optimized.conf`, `ollama-gpu-boot-order.conf`, `btc-trading-agent-validate.conf`, `nginx-dns-over-tls.conf`, `pihole-ipv6-dns-fix.override.conf`, `radvd.conf`) | Não estão numa árvore `<unit>.d/`; o destino no host é ambíguo. Instalar no lugar errado é pior que não instalar. |

Para tornar um arquivo sincronizável, acrescente o caminho a
`deploy/systemd-dropins-sync.allowlist` — o deploy, o verificador, o gatilho do
workflow e os testes leem o mesmo arquivo. Antes de listar, **compare com o
host**: se ele estiver à frente, traga a mudança para o repo primeiro (foi o
caso de `zz-dual-gpu-routing.conf` e `zzzz-warmup-curl.conf`). Um arquivo
versionado mas fora da allowlist aparece como `not_synced` no verificador — a
omissão é intencional e fica documentada na própria allowlist.

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

## Estado da paridade (2026-07-25)

Após a captura, `check_systemd_dropin_drift.py` contra o host dá:

```
Σ ok=36 missing=1 differs=2 redacted=1 host_only=0
```

As três divergências restantes são **decisões pendentes**, não drift acidental —
o deploy vai impor o lado do repo em cada uma:

| Arquivo | Host | Repo | Efeito de deployar |
|---|---|---|---|
| `crypto-agent@BTC_USDT_aggressive.service.d/zz-direct-ollama.conf` | `OLLAMA_PLAN_MODEL=trading-analyst` | `lfm2.5-fast:gpu1` | **Muda o modelo de plano do perfil agressivo** de GPU0 (trading-analyst, 12GB) para GPU1 (lfm2.5, 2GB). Ambos estão quentes hoje (`/api/ps`), então nenhum dos dois causa 503 — é escolha de comportamento, com dinheiro real. |
| `crypto-agent@.service.d/ollama-timeout.conf` | comentário cita `gemma3-fast` | comentário cita `lfm2.5-fast` | Só comentário; nenhum `Environment=` muda. |
| `crypto-agent@.service.d/cpuaffinity.conf` | não existe | `CPUAffinity=2-15` | Instala o arquivo. Inerte na prática: `zz-proxy-protect.conf` vem depois na ordem alfabética e faz `CPUAffinity=` + `14-15`. |

> ⚠️ A premissa original — "produção segue com `gemma3-fast:gpu1` depois do
> PR #246" — **não se confirmou**. O host está com `trading-analyst`, um
> terceiro valor, alterado ao vivo. O drift era bidirecional: em
> `zz-dual-gpu-routing.conf` e `zzzz-warmup-curl.conf` era o **host** que
> estava à frente (o repo teria removido `OLLAMA_NAS_HOST` e
> `GPU_COORD_POLL_INTERVAL_SEC` do coordenador). Por isso a captura veio antes
> do deploy.

Nota: `OLLAMA_NAS_HOST=http://192.168.15.4:11436` está configurado no
coordenador mas **não responde** (curl → `000`). Backend morto, a limpar em
mudança própria.
