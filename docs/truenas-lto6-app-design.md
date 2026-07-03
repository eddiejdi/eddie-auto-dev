# TrueNAS LTO-6 App — Design & Plano de Implementação

> Status: **proposta** (2026-06-29) · Alvo: TrueNAS SCALE 24.10.2.4 "Electric Eel" · NAS Optiplex `192.168.15.4`

App de catálogo do TrueNAS que empacota **instalação + suporte + monitoramento** de fitas
LTO-6 (LTFS) como uma aplicação publicável na App Store (aba *Discover*), com dashboards no
padrão dos projetos e a **área de buffer pré-tape como pré-requisito obrigatório**.

---

## 1. Investigação do servidor (fatos coletados)

| Item | Valor descoberto |
|------|------------------|
| TrueNAS | 24.10.2.4 (Electric Eel), **Docker** (não k3s) |
| Catálogo | único `TRUENAS` em `/mnt/.ix-apps/truenas_catalog` (repo git) — trains `community/stable/enterprise` |
| `catalog.create` | **não existe** nesta versão (UI multi-catálogo removida na EE) |
| `app.create` | existe → suporta **Custom App** (docker-compose) e apps de catálogo |
| Estrutura de app | `ix-dev/<train>/<app>/` (fonte) → renderizado em `trains/<train>/<app>/<versão>/` com `item.yaml`, `app.yaml`, `questions.yaml`, `ix_values.yaml`, `templates/docker-compose.yaml` |
| FUSE | `/dev/fuse` presente, `fuse` em `/proc/filesystems` |
| Drives | `sg4`/`nst1` → `ltfs-lto6` (SG1R26), `sg2`/`nst0` → `ltfs-lto6b`; grupo `tape` |
| Buffer pré-tape | `tank/pretape/lto6-cache` (134G) + `tank/pretape/lto6-cache-sg1` (138G) — exportado via NFS/CIFS ao homelab |
| Tooling LTFS | `/var/db/ltfs-tools/`: `ltfs_recovery.py`, `ltfs-fc-stable-start`, `ltfs-lto6-stop`, `lto6-resolve-device`, `lto6b-resolve-device`, `tape_dual_recovery.py`; binários patcheados em `/var/db/ltfs-patched/bin/` |
| Env | `/etc/default/ltfs-lto6`, `ltfs-lto6b`, `ltfs-recovery` |
| Exporters | `export-lto6-metrics.sh` → textfile `.prom` no node-exporter; `tape-component-quality` exporter na :9124 |
| Dashboards | `grafana/dashboards/tape-component-quality.json` — painéis em PT, diagnóstico AI via Ollama 1x/dia |
| Prometheus | jobs `nas-node-exporter` (:9100), `tape-component-quality` (:9124) já apontam para `.4` |

### Decisões tomadas com o usuário
- **Arquitetura: control-plane.** O mount LTFS FUSE permanece como serviço systemd **no host**
  (robusto com FC, como hoje). O app é o **plano de controle**: orchestrator, button-watch,
  exporters e dashboards, com privilégios para gerenciar o host.
- **Git dedicado:** novo repo **`eddiejdi/truenas-lto6-app`** em formato de catálogo TrueNAS.

---

## 2. Por que control-plane (e não LTFS dentro do container)

O LTFS é um mount FUSE que precisa estar **visível no host** (`/mnt/tape/lto6`) para que NFS/CIFS
e o pipeline de drain o consumam. Containerizar o mount exige `privileged` + bind-propagation
`rshared` + repasse de `/dev/sg`, `/dev/nst`, `/dev/fuse` + `CAP_SYS_ADMIN`, e é frágil em
remount/recovery com a HBA QLogic FC (lições registradas: `[[feedback_ltfs_fc_transport_failure]]`,
`[[feedback_ltfs_concurrent_mount_race]]`).

**O app não reinventa o mount** — ele instala e orquestra o stack que já é maduro no host. Isso
preserva todo o conhecimento acumulado (orchestrator-first, locks exclusivos, self-heal).

---

## 3. Arquitetura do app

```
┌──────────────────────── TrueNAS App: "LTO-6 Tape Manager" ────────────────────────┐
│                                                                                    │
│  container: lto6-control-plane  (privileged, host PID, /dev/sg* /dev/nst* /dev/fuse)│
│   ├─ installer (init, roda 1x):                                                    │
│   │    instala binários LTFS, ltfs_recovery.py, button-watch e units systemd no    │
│   │    host via nsenter; cria env files; valida buffer pré-tape                    │
│   ├─ orchestrator API (HTTP :9877)  → wraps ltfs_recovery.py                       │
│   ├─ ltfs_button_watch.py           → auto-mount/eject por botão (já criado)        │
│   └─ exporter (:9125)               → métricas Prometheus do stack + buffer        │
│                                                                                    │
│  storage (questions.yaml):                                                         │
│   ├─ [OBRIGATÓRIO] buffer pré-tape  → host path tank/pretape/lto6-cache            │
│   ├─ mount point host               → /mnt/tape/lto6                               │
│   └─ catálogo/cursores              → ix_volume                                    │
│                                                                                    │
│  host systemd (instalado pelo app, roda fora do container):                        │
│   └─ ltfs-lto6.service (FUSE mount)  ← gerenciado pelo orchestrator                │
└────────────────────────────────────────────────────────────────────────────────────┘
            │ scrape :9125                          │ provisioning
            ▼                                        ▼
      Prometheus (homelab)                    Grafana (homelab) — dashboard LTO-6
```

### Pré-requisito de buffer (exigência do usuário)
`questions.yaml` declara o dataset de **buffer pré-tape como storage obrigatório** (não
opcional). O installer **falha o deploy** se:
- o dataset de buffer não for informado, ou
- o espaço livre estiver abaixo do `min_free` (default 30 GiB — alinhado ao buffer-gate
  existente, `[[feedback_buffer_gate_continuous]]`).

A gauge de buffer vira painel de primeira classe no dashboard (thresholds gate=80%, kill=88%).

---

## 4. Estrutura do repositório `truenas-lto6-app`

```
truenas-lto6-app/
├── README.md
├── catalog.json                       # metadata do catálogo (label, trains)
├── ix-dev/
│   └── stable/
│       └── lto6-tape/
│           ├── item.yaml               # categorias, ícone, tags, screenshots
│           ├── app.yaml                # versão, maintainers, capabilities, min_scale_version
│           ├── questions.yaml          # UI: devices, buffer (obrigatório), telegram, portas
│           ├── ix_values.yaml          # defaults
│           ├── templates/
│           │   └── docker-compose.yaml # render Jinja (padrão ix_lib.base.render)
│           └── templates/test_values/  # valores p/ CI de render
├── images/
│   └── lto6-control-plane/
│       ├── Dockerfile                  # base debian + ltfs patcheado + python tooling
│       └── rootfs/
│           ├── installer.sh            # bootstrap host (nsenter) + valida buffer
│           ├── orchestrator_api.py     # HTTP wrapper de ltfs_recovery.py
│           ├── ltfs_button_watch.py    # (extraído deste repo)
│           └── exporter.py             # métricas Prometheus
├── host-assets/                        # extraído do servidor /var/db/ltfs-tools/
│   ├── ltfs_recovery.py
│   ├── ltfs-fc-stable-start
│   ├── ltfs-lto6-stop
│   ├── lto6-resolve-device
│   ├── lto6b-resolve-device
│   └── systemd/ (ltfs-lto6.service, ltfs-button-watch.service, ...)
├── grafana/
│   └── dashboards/lto6-tape-manager.json   # padrão tape-component-quality
└── .github/workflows/
    ├── ci-render.yml                   # valida render do catálogo + lint
    └── build-image.yml                 # build/push da imagem control-plane
```

### Extração do servidor (o "git específico desse contexto")
Script de extração (one-shot) que puxa do NAS para `host-assets/`:
```
/var/db/ltfs-tools/{ltfs_recovery.py,ltfs-fc-stable-start,ltfs-lto6-stop,
                    lto6-resolve-device,lto6b-resolve-device,tape_dual_recovery.py}
/etc/default/{ltfs-lto6,ltfs-lto6b,ltfs-recovery}   (sanitizado — sem segredos)
/etc/systemd/system/ltfs-lto6*.service (+ drop-ins)
```
Segredos (Telegram token) **não** entram no git — viram `questions.yaml` → env no deploy.

---

## 5. Publicação na App Store (Discover)

Como `catalog.create` não existe na 24.10, há dois caminhos. O plano entrega **ambos**, em ordem:

1. **Caminho primário — train local no catálogo TRUENAS.**
   Renderiza o app de `ix-dev/` para `trains/community/lto6-tape/<versão>/` e injeta no
   repo de catálogo local (`/mnt/.ix-apps/truenas_catalog`) via overlay git, depois
   `midclt call catalog.sync`. O app passa a aparecer em *Discover → Community*.
   *Risco:* `catalog.sync` pode reescrever o repo a partir do remoto oficial; mitigação =
   manter o app como commit overlay + serviço de re-aplicação pós-sync (selfheal),
   padrão já usado no projeto.

2. **Caminho de fallback — Custom App (docker-compose).**
   `app.create` com o docker-compose renderizado. Aparece em *Installed*, não em *Discover*,
   mas instala 100% do stack. Serve como instalação imediata e teste de fumaça.

> Recomendação: validar primeiro via **Custom App** (rápido), depois promover ao **train local**
> para a experiência de "app store" pedida.

---

## 6. Dashboards (padrão dos projetos)

`lto6-tape-manager.json` espelhando `tape-component-quality.json`:
- Painéis em **PT**, gauge de qualidade geral, *Última Coleta*.
- **Buffer pré-tape** (gauge + tendência, thresholds 80/88%) — primeira classe.
- Estado do mount (`nas_ltfs_mount_up`), serviço (`nas_ltfs_service_up`), temp do drive.
- Throughput de drain, posição da fita, contadores de erro FC.
- Card de **diagnóstico AI (Ollama)** 1x/dia, como no dashboard de component-quality.
- Provisionado via `monitoring/grafana/provisioning/dashboards/` + scrape job novo (:9125).

---

## 7. Métricas novas do exporter (:9125)

```
lto6_app_buffer_bytes_free{dataset,drive}
lto6_app_buffer_pct_used{dataset,drive}
lto6_app_buffer_gate_ok{drive}              # 1 se < 80%
lto6_app_mount_up{drive} / lto6_app_service_up{drive}
lto6_app_drive_temp_celsius{drive}
lto6_app_button_watch_up
lto6_app_orchestrator_lock_held{operation}
lto6_app_last_mount_timestamp / lto6_app_last_eject_timestamp
```

---

## 8. Plano de implementação (fases)

| # | Fase | Entregável | Verificação |
|---|------|-----------|-------------|
| 1 | **Bootstrap repo** | `truenas-lto6-app` criado (eddiejdi), skeleton + README | repo cloná­vel |
| 2 | **Extração host** | `extract-host-assets.sh` puxa tooling do `.4` (sanitizado) | `host-assets/` populado, sem segredos |
| 3 | **Imagem control-plane** | Dockerfile + installer.sh + orchestrator_api.py + exporter.py + button-watch | `docker build` ok, `--help` dos tools |
| 4 | **App de catálogo** | item/app/questions/ix_values + template docker-compose | render local passa no CI |
| 5 | **Buffer pré-req** | validação obrigatória no questions.yaml + installer (min_free) | deploy falha sem buffer |
| 6 | **Dashboard + scrape** | `lto6-tape-manager.json` + job Prometheus :9125 | painéis com dados |
| 7 | **Publicação** | Custom App (fallback) → train local (primário) + selfheal pós-sync | app em *Discover* |
| 8 | **CI/CD** | `ci-render.yml` + `build-image.yml` + deploy guardrail (`nas-gh-deploy-guard`) | workflow verde |

### Restrições de segurança respeitadas
- Deploy no `.4` **só via pipeline** (`nas-gh-deploy-guard`) — não SCP direto
  (`[[feedback_deploy_requires_regression]]`).
- Operações de fita **sempre via orchestrator** (`[[feedback_ltfs_tape_confirm_before_action]]`).
- Segredos via `questions.yaml`/secrets agent, nunca no git
  (`[[feedback_no_credential_changes]]`).
- Regressão antes de qualquer deploy; falhas apresentadas ao usuário.

---

## 9. Riscos & mitigações

| Risco | Mitigação |
|-------|-----------|
| `catalog.sync` sobrescreve o app overlay | selfheal de re-aplicação pós-sync; preferir Custom App p/ produção estável |
| Container privileged + FC instável | mount fica no host; container só orquestra via nsenter/SSH |
| Buffer cheio trava pipeline (`[[project_lto_nas_root_full_20260601]]`) | gate obrigatório no installer + watchdog + painel |
| Upgrade do TrueNAS quebra o catálogo local | versionar `min_scale_version`; CI de render por versão |
| Dois drives (sg4/sg2) | app multi-instância ou seletor de drive no questions.yaml |

---

# Apêndice — Especificações concretas

> Esqueletos prontos para implementação. Servem de contrato entre as fases.

## A. `questions.yaml` (UI de instalação)

Grupos: **Drive**, **Buffer Pré-Tape (obrigatório)**, **Orquestração**, **Notificações**, **Rede/Recursos**.

```yaml
groups:
  - name: Drive Configuration
    description: Seleção do drive LTO e devices SCSI
  - name: Pre-Tape Buffer            # PRÉ-REQUISITO
    description: Área de buffer obrigatória antes da gravação em fita
  - name: Orchestration
    description: Mount point, janela de uso e self-heal
  - name: Notifications
    description: Telegram para eventos de mount/eject/recovery
  - name: Network Configuration
    description: Portas do orchestrator API e do exporter

questions:
  - variable: drive
    group: Drive Configuration
    label: ""
    schema:
      type: dict
      attrs:
        - variable: id
          label: Drive
          schema: { type: string, required: true, default: lto6,
                    enum: [ {value: lto6, description: "LTO-6 (sg4/nst1)"},
                            {value: lto6b, description: "LTO-6b (sg2/nst0)"} ] }
        - variable: sg_device
          label: SCSI generic (/dev/sgN)
          schema: { type: string, required: true, default: /dev/sg4 }
        - variable: nst_device
          label: Tape device (/dev/nstN)
          schema: { type: string, required: true, default: /dev/nst1 }

  - variable: buffer                  # ── PRÉ-REQUISITO OBRIGATÓRIO ──
    group: Pre-Tape Buffer
    label: ""
    schema:
      type: dict
      attrs:
        - variable: host_path
          label: Dataset de buffer pré-tape
          description: Host path do dataset (ex: /mnt/tank/pretape/lto6-cache). Obrigatório.
          schema:
            type: hostpath
            required: true              # <- deploy falha sem isto
        - variable: min_free_gib
          label: Espaço livre mínimo (GiB)
          description: Gate — mount é bloqueado se o buffer cair abaixo disto.
          schema: { type: int, required: true, default: 30, min: 10 }
        - variable: gate_pct
          label: Gate de uso (%)
          schema: { type: int, default: 80, min: 50, max: 95 }
        - variable: kill_pct
          label: Abort de uso (%)
          schema: { type: int, default: 88, min: 60, max: 99 }

  - variable: orchestration
    group: Orchestration
    label: ""
    schema:
      type: dict
      attrs:
        - variable: mount_point
          schema: { type: hostpath, required: true, default: /mnt/tape/lto6 }
        - variable: usage_window_start
          schema: { type: string, default: "02:00" }
        - variable: usage_window_end
          schema: { type: string, default: "04:00" }
        - variable: install_host_units
          label: Instalar units systemd no host (control-plane)
          schema: { type: boolean, default: true }

  - variable: notifications
    group: Notifications
    label: ""
    schema:
      type: dict
      attrs:
        - variable: telegram_bot_token
          schema: { type: string, default: "", private: true }   # nunca no git
        - variable: telegram_chat_id
          schema: { type: string, default: "" }

  - variable: network
    group: Network Configuration
    label: ""
    schema:
      type: dict
      attrs:
        - variable: orchestrator_port
          schema: { type: int, default: 9877 }
        - variable: exporter_port
          schema: { type: int, default: 9125 }
```

## B. `templates/docker-compose.yaml` (render Jinja)

Segue o padrão `ix_lib.base.render.Render`. Pontos-chave (control-plane → precisa do host):

```jinja
{% set tpl = ix_lib.base.render.Render(values) %}
{% set c1 = tpl.add_container(values.consts.app_name, "image") %}

{# control-plane: acesso ao host #}
{% do c1.set_privileged(true) %}
{% do c1.set_network_mode("host") %}
{% do c1.add_caps(["SYS_ADMIN"]) %}
{% do c1.add_device("/dev/fuse", "/dev/fuse") %}
{% do c1.add_device(values.drive.sg_device, values.drive.sg_device) %}
{% do c1.add_device(values.drive.nst_device, values.drive.nst_device) %}

{# buffer pré-tape — bind do host, propagação rshared p/ enxergar o mount LTFS #}
{% do c1.add_storage(values.buffer.host_path,
     {"type":"host_path","host_path_config":{"path":values.buffer.host_path},
      "propagation":"rshared"}) %}
{% do c1.add_storage(values.orchestration.mount_point,
     {"type":"host_path","host_path_config":{"path":values.orchestration.mount_point},
      "propagation":"rshared"}) %}

{# nsenter precisa de PID host p/ instalar units e gerenciar systemd #}
{% do c1.set_pid_mode("host") %}

{% do c1.environment.add_env("LTFS_DEVICE", values.drive.sg_device) %}
{% do c1.environment.add_env("LTFS_TAPE_DEVICE", values.drive.nst_device) %}
{% do c1.environment.add_env("LTFS_MOUNT_POINT", values.orchestration.mount_point) %}
{% do c1.environment.add_env("BUFFER_PATH", values.buffer.host_path) %}
{% do c1.environment.add_env("BUFFER_MIN_FREE_GIB", values.buffer.min_free_gib) %}
{% do c1.environment.add_env("TELEGRAM_BOT_TOKEN", values.notifications.telegram_bot_token) %}
{% do c1.environment.add_env("TELEGRAM_CHAT_ID", values.notifications.telegram_chat_id) %}

{% do c1.healthcheck.set_custom_test(
     ["CMD","curl","-fsS","http://localhost:%d/health"|format(values.network.orchestrator_port)]) %}
{{ tpl.render() | tojson }}
```

> Decisão de implementação: `propagation: rshared` + `pid: host` + `privileged` são o mínimo
> para o container instalar units no host e enxergar o mount FUSE. Se a base lib do catálogo
> não expuser `propagation`, cai-se para o **Custom App** (docker-compose cru permite
> `volumes: [/mnt/tape/lto6:/mnt/tape/lto6:rshared]` diretamente).

## C. `installer.sh` (init do container — fluxo)

```
1. PRÉ-REQUISITO BUFFER (falha cedo):
   - test -d "$BUFFER_PATH"                       || exit 90 "buffer ausente"
   - free=$(df --output=avail -BG "$BUFFER_PATH") || exit 91
   - [ "$free" -ge "$BUFFER_MIN_FREE_GIB" ]       || exit 92 "buffer cheio"
2. INSTALA BINÁRIOS LTFS no host (se install_host_units):
   - nsenter -t 1 -m -- cp host-assets/ltfs-patched → /var/db/ltfs-patched   (se ausente)
   - install ltfs_recovery.py        → /usr/local/tools/
   - install ltfs-fc-stable-start, ltfs-lto6-stop, resolvers → /usr/local/sbin/
   - render /etc/default/ltfs-<drive> a partir das envs (sem segredos no git)
3. INSTALA UNITS no host via nsenter:
   - ltfs-lto6.service, ltfs-button-watch.service
   - systemctl daemon-reload && enable --now ltfs-button-watch.service
4. NÃO monta a fita aqui — entrega ao orchestrator (orchestrated-mount) sob demanda/janela.
5. exec → supervisor (orchestrator_api + button_watch + exporter)
```

## D. `orchestrator_api.py` (HTTP :9877) — superfície

Wrapper fino sobre `ltfs_recovery.py` (que já tem todos os modos). Endpoints:

| Método | Rota | Ação `ltfs_recovery.py` |
|--------|------|--------------------------|
| GET  | `/health` | processo vivo |
| GET  | `/status` | `--check` + estado do buffer |
| POST | `/mount`  | `--orchestrated-mount` (valida buffer antes) |
| POST | `/unmount`| `--orchestrated-stop` |
| POST | `/eject`  | `--orchestrated-stop` + eject mecânico (reusa button-watch) |
| POST | `/deep-recovery` | `--deep-recovery` |
| GET  | `/diagnose` | `--diagnose` |
| GET  | `/cursor` | `--cursor-list` |

Toda rota de fita **revalida o gate de buffer** e respeita o lock exclusivo
(`LTFS_ORCH_LOCK`). Sem segredos em log (`<think>`/whitespace já tratados no projeto).

## E. `extract-host-assets.sh` (Fase 2 — extração sanitizada)

```bash
# Roda LOCAL, lê via SSH do .4 (read-only). NÃO escreve no servidor.
SRC=root@192.168.15.4
declare -a FILES=(
  /var/db/ltfs-tools/ltfs_recovery.py
  /var/db/ltfs-tools/ltfs-fc-stable-start
  /var/db/ltfs-tools/ltfs-lto6-stop
  /var/db/ltfs-tools/lto6-resolve-device
  /var/db/ltfs-tools/lto6b-resolve-device
  /var/db/ltfs-tools/tape_dual_recovery.py
)
for f in "${FILES[@]}"; do scp "$SRC:$f" "host-assets/$(basename "$f")"; done
# env files: copiar e SANITIZAR (remover TELEGRAM_*_TOKEN, senhas)
ssh "$SRC" "cat /etc/default/ltfs-lto6"  | grep -vE 'TOKEN|PASSWORD|SECRET' > host-assets/env/ltfs-lto6.env
# systemd units (já versionados neste repo → copiar de systemd/)
cp ../eddie-auto-dev/systemd/ltfs-lto6.service          host-assets/systemd/
cp ../eddie-auto-dev/systemd/ltfs-button-watch.service  host-assets/systemd/
```

## F. CI workflows do repo dedicado

- `ci-render.yml` — render do catálogo (`ix-dev` → `trains`) + lint YAML + `test_values`.
- `build-image.yml` — `docker build images/lto6-control-plane`, push para registry
  (ghcr.io/eddiejdi/lto6-control-plane), tag = versão do app.yaml.
- `deploy.yml` — promove ao NAS via `nas-gh-deploy-guard` (runner self-hosted `nas`),
  nunca SCP direto; regressão obrigatória antes.

## G. Mapa de extração ↔ destino no app

| Origem (servidor/repo) | Destino no app |
|------------------------|----------------|
| `.4:/var/db/ltfs-tools/ltfs_recovery.py` | `images/.../rootfs/` + `host-assets/` |
| `.4:/var/db/ltfs-tools/ltfs-fc-stable-start` | `host-assets/` (instalado no host) |
| `.4:/var/db/ltfs-patched/bin/{ltfs,ltfsck,mkltfs}` | imagem Docker (camada base) |
| `eddie-auto-dev/tools/ltfs_button_watch.py` | `images/.../rootfs/` |
| `eddie-auto-dev/systemd/ltfs-button-watch.service` | `host-assets/systemd/` |
| `eddie-auto-dev/grafana/dashboards/tape-component-quality.json` | base p/ `grafana/dashboards/lto6-tape-manager.json` |
| `.4:/etc/default/ltfs-*` (sanitizado) | template de env no `installer.sh` |
```
