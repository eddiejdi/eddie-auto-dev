# Incidente — RTX 2060 da NAS "frozen recorrente" — 2026-07-31

## Resumo Executivo

Dono reportou congelamentos recorrentes na RTX 2060 SUPER da NAS
(`nas-optiplex`, usada pela persona-free do WhatsApp e pelo shadow-eval do
trading-analyst). Investigação encontrou dois problemas **independentes**
na mesma GPU:

1. `ollama-metrics-nas.service` (exporter de métricas) em **loop de crash
   havia muito tempo** — contador de restart em `7366` e subindo, a cada
   ~5s, por uma imagem Docker com layer `overlay2` corrompida.
2. `ollama-nas.service` (o motor de inferência real) recarregava o
   **mesmo** modelo (`dolphin-2.9-llama3-8b`, persona-free) do zero
   dezenas de vezes por dia — 130+ recargas em 23h — cada uma levando
   ~1-1,5min. Esse é o "freeze" percebido pelo dono: toda mensagem
   enviada mais de 10min depois da anterior esperava o cold-reload
   completar antes de receber resposta.

Causa do item 2: `OLLAMA_KEEP_ALIVE=10m`, configurado em 2026-07-27 para
resolver um problema diferente (3 timers sintéticos mantendo a GPU em
P2/45W 24/7). **Esses 3 timers já tinham sido removidos** antes deste
incidente — sobrou só o efeito colateral do `KEEP_ALIVE` curto, sem o
motivo original que o justificava.

---

## Sintoma Observado

- Dono: "minha 2060 está frozen recorrente".
- `nvidia-smi` no host respondia normalmente (driver não estava
  travado) — o "freeze" era no nível de latência de resposta do Ollama,
  não do driver/GPU em si.
- `ollama-nas.service`: `"failure during GPU discovery" error="failed to
  finish discovery before timeout"` — 22 ocorrências em 24h.
- `ollama-metrics-nas.service`: `systemctl status` mostrava
  `activating (auto-restart)`, restart counter em 7366+.

---

## Causa Raiz

### 1. `ollama-metrics-nas.service` — layer Docker corrompida

```
docker: Error response from daemon: open
/mnt/.ix-apps/docker/overlay2/e81699b67.../.tmp-committed...:
no such file or directory
```

O diretório `overlay2` referenciado pelos metadados internos do Docker
simplesmente não existia mais (`ls`: no such file or directory), enquanto
o dataset `.ix-apps` tinha 123GB livres (não era espaço em disco — era
metadata desincronizada, provavelmente de um reboot anterior não-limpo
desta NAS, já documentado em incidentes de fonte de alimentação
anteriores).

### 2. `ollama-nas.service` — `KEEP_ALIVE` curto demais pro padrão real de uso

Log confirma que é **sempre o mesmo modelo** recarregando (não disputa
entre modelos diferentes):

```
$ journalctl -u ollama-nas --since "3 hours ago" | grep "general.name str"
... general.name str = dolphin-2.9-llama3-8b   (repetido 40+ vezes)
```

`OLLAMA_KEEP_ALIVE=10m` (drop-in `zzzz-idle-power.conf`, 2026-07-27)
descarrega o modelo da VRAM 10 minutos após o último uso. Como mensagens
reais do WhatsApp chegam espaçadas (10-30min entre elas — padrão humano
normal), **a maioria das mensagens encontrava o modelo já descarregado**,
forçando um cold-reload (`load_tensors... mmap=false`, ~1-1,5min) antes de
gerar a primeira resposta.

O `10m` foi motivado originalmente por 3 timers sintéticos
(`ollama-warmup-nas.timer`, `nas-ollama-load.timer`,
`nas-ai-assessor` a cada 5min) que geravam tráfego artificial sem
trabalho real, prendendo a GPU em P2/45,6W permanentemente. Esses 3
timers **já não existem** (`systemctl list-timers` não retorna nenhum) —
provavelmente removidos numa limpeza anterior sem reverter o
`KEEP_ALIVE` que os compensava.

---

## Correções Aplicadas

### 1. Metrics exporter

```bash
ssh nas "docker rmi ghcr.io/norskhelsenett/ollama-metrics:latest"
ssh nas "docker pull ghcr.io/norskhelsenett/ollama-metrics:latest"
ssh nas "systemctl reset-failed ollama-metrics-nas.service"
ssh nas "systemctl start ollama-metrics-nas.service"
```

Resultado: `NRestarts=0`, `ActiveState=active`, `/metrics` respondendo.

### 2. `OLLAMA_KEEP_ALIVE`

Drop-in `ollama-nas.service.d/zzzz-idle-power.conf` atualizado:

```diff
- Environment=OLLAMA_KEEP_ALIVE=10m
+ Environment=OLLAMA_KEEP_ALIVE=-1
  Environment=OLLAMA_MAX_LOADED_MODELS=1
  ExecStartPost=
```

`MAX_LOADED_MODELS=1` mantido (só 1 modelo roda nesta GPU; proteção
contra overcommit de VRAM). Backup do drop-in anterior salvo
(`zzzz-idle-power.conf.bak.20260731`). `daemon-reload` +
`systemctl restart ollama-nas.service`.

**Por que `-1` não reintroduz o custo original**: o problema documentado
em 2026-07-27 era o *tráfego periódico* (P2/45,6W), não a residência do
modelo em si (`GPU sem tráfego, modelo residente em VRAM .. P8, 300MHz,
18W` — já medido na época). Sem os 3 timers sintéticos, a GPU volta a
descer pra P8 idle normalmente entre mensagens reais; só não descarrega
mais o modelo por descarregar.

---

## Validação Pós-Correção

```
$ systemctl show ollama-metrics-nas.service -p NRestarts
NRestarts=0

$ curl -s http://localhost:11436/api/version
{"version":"0.17.6"}

$ systemctl show ollama-nas.service -p Environment | grep KEEP_ALIVE
OLLAMA_KEEP_ALIVE=-1

$ nvidia-smi --query-gpu=power.draw,pstate,memory.used,utilization.gpu --format=csv,noheader
21.54 W, P8, 1 MiB, 0 %
```

GPU em P8/idle logo após restart (modelo ainda não recarregado — primeira
mensagem real vai carregar uma última vez e permanecer residente).

## Pendências Não Fechadas

- Validação de que o freeze não recorre depende da **próxima mensagem
  real do dono** — não foi possível confirmar em tempo real dentro desta
  sessão. Se voltar a travar após isso, a causa é outra (não o
  `KEEP_ALIVE`).
- Corrupção de metadata do Docker no `.ix-apps` pode ter causa raiz mais
  profunda (histórico de reboots não-limpos desta NAS já documentado em
  outros incidentes) — não investigada aqui além do reset pontual.

---

## Lições Operacionais

1. **"Frozen" em GPU nem sempre é o driver travado.** `nvidia-smi`
   respondendo normalmente não descarta latência de cold-reload de
   modelo como causa do sintoma percebido pelo usuário.
2. **Otimização de idle-power e latência de resposta competem.** Reduzir
   `KEEP_ALIVE` economiza energia em idle longo, mas cada reload custa
   ~1-1,5min de silêncio pro usuário — se o padrão real de uso é mais
   frequente que o timeout, o trade vira prejuízo líquido de UX sem
   ganho real (a causa do consumo alto já tinha sido removida).
3. **Configuração motivada por um sintoma específico precisa ser
   revisitada quando esse sintoma original desaparece.** O `KEEP_ALIVE=10m`
   ficou "órfão" depois que os timers que ele compensava foram removidos —
   ninguém voltou a reavaliar se o valor ainda fazia sentido.
4. **Contador de restart do systemd (`NRestarts`) é o primeiro lugar pra
   olhar** quando um serviço parece "flaky" — 7366 reinícios não gera
   alerta óbvio se o serviço eventualmente fica `active (running)` em
   qualquer snapshot pontual.

---

## Comandos Úteis para Diagnóstico Futuro

Ver se o modelo está residente ou vai recarregar na próxima chamada:

```bash
ssh nas "curl -s http://localhost:11436/api/ps"
```

Contar recargas do mesmo modelo num período:

```bash
ssh nas "journalctl -u ollama-nas.service --since '24 hours ago' \
  --no-pager | grep -c 'loaded runners'"
```

Ver estado de power/pstate da GPU:

```bash
ssh nas "nvidia-smi --query-gpu=power.draw,pstate,memory.used,utilization.gpu --format=csv,noheader"
```

Ver se o metrics exporter está em crash loop:

```bash
ssh nas "systemctl show ollama-metrics-nas.service -p NRestarts -p ActiveState"
```
