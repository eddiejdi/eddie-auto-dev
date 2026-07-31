# Incidente — Cloud FT (RunPod) trava em cota de disco + job morto silenciosamente — 2026-07-31

## Resumo Executivo

O painel `cloud-ft-runpod` mostrava `eddie-persona-free` como `fail` e
`eddie-persona-safe` como `running` indefinidamente. Investigação encontrou
dois problemas independentes no mesmo pod RunPod:

1. **`eddie-persona-free` falhou de verdade**: o LoRA treinou normalmente
   (loss 0.2856), mas o passo de merge fp16 estourou a cota de **40GB** do
   volume do pod (`safetensors ... Disk quota exceeded`).
2. **`eddie-persona-safe` estava morto, não rodando**: o processo de treino
   parou silenciosamente no step 50/100 (sem traceback, sem marcador
   `EXIT` no log), muito provavelmente por SIGHUP de uma sessão SSH anterior
   que não usou `nohup`/`setsid`. O pod ficou ~3h ocioso gastando US$0,69/h
   à toa, enquanto o Grafana continuava mostrando "running".

Um fix parcial (`merge=false` para todos os 4 jobs + `pod_disk_hygiene.sh`)
já tinha sido commitado no repo `homelab-cloud-ft` (`44bbd61`, 15:43) por
uma sessão anterior, mas **nunca chegou a ser implantado no bundle ao vivo
do pod** — os arquivos `run_job.sh`, `pod_disk_hygiene.sh` e `jobs.json` na
raiz do `/workspace` do pod estavam corrompidos (preenchidos com bytes
`\x00`), evidência de uma escrita via SSH interrompida no meio.

---

## Sintoma Observado

- Painel Grafana `cloud-ft-runpod` (`viewPanel=panel-13`, "Job status"):
  `eddie-persona-free=3 (fail)`, `eddie-persona-safe=1 (running)` parado.
- `ps aux` no pod: nenhum processo `python3`/`run_job.sh` rodando.
- GPU do pod: `2 MiB` usados, `0%` util (ociosa).
- Log de treino parado em `50/100` sem marcador `EXIT`.

---

## Causa Raiz

### 1. Merge fp16 estoura a cota do volume do pod

```
safetensors._safetensors_rust.SafetensorError: Error while serializing:
I/O error: Disk quota exceeded (os error 122)
```

`df -h /workspace` no pod mostra um pool MooseFS compartilhado de 1.2PB —
enganoso. A cota real do **volume atribuído a este pod** é fixa em 40GB
(`volumeInGb: 40` via API RunPod `GET /pods/{id}`), não o pool inteiro.
Merge fp16 de um modelo 8B escreve ~15-16GB de uma vez; combinado com
`hf-cache` (16GB, modelo base cacheado) e bundles acumulados de tentativas
anteriores, estourava a cota.

### 2. Processo de treino morto sem log de causa

`run_remaining_jobs.sh` chama `bash run_job.sh "$job" >> log 2>&1` em
foreground dentro de outro script. Se o script pai foi lançado via SSH sem
`nohup`/`setsid`/`disown`, fechar a sessão SSH manda SIGHUP para toda a
árvore de processos filhos, matando o treino no meio sem deixar traceback.

### 3. Fix commitado nunca implantado no pod

Commit `44bbd61` (`homelab-cloud-ft`, 15:43) já continha o fix correto:
`merge=false` para os 4 jobs, `FT_SAVE_TOTAL_LIMIT=1`, `run_job.sh` com
`FT_SKIP_MERGE`, `pod_disk_hygiene.sh` funcional, exclusão de merges
incompletos no rsync. Mas os arquivos correspondentes no pod
(`/workspace/run_job.sh`, `/workspace/pod_disk_hygiene.sh`,
`/workspace/jobs.json`) estavam com conteúdo 100% `\x00` — uma escrita via
SSH (provavelmente um heredoc) foi cortada no meio, deixando o arquivo do
tamanho certo mas vazio de conteúdo real.

Cópias íntegras sobreviveram dentro do bundle
(`/workspace/ft-bundle-20260731-141544/{run_job.sh,jobs.json}`), o que
permitiu recuperação sem reconstrução manual.

---

## Correções Aplicadas

### No pod (ao vivo)

1. `jobs.json`: `merge=false` para os 4 jobs (restaurado a partir da versão
   canônica do repo, não só os 2 que tinham sido corrigidos manualmente
   antes).
2. `run_job.sh` / `pod_disk_hygiene.sh`: substituídos pelas versões
   canônicas do repo `homelab-cloud-ft` (`FT_SKIP_MERGE`, limpeza de
   `merged_model/`, checkpoints de jobs concluídos, arquivos incompletos do
   hf-cache).
3. `eddie-persona-free` e `eddie-persona-safe` relançados via
   `setsid nohup bash run_remaining_nomerge.sh ... & disown` — sobrevive a
   queda de SSH.
4. `pod_disk_hygiene.sh` rodado ao vivo: bundle caiu de ~2GB para 731MB.

### No repositório `homelab-cloud-ft`

Commit `993a6fb` + `e77b75e` (`cloud_ft/orchestrator.py`,
`cloud_ft/download_results.py`): sync incremental por job.

- Antes: o orquestrador só baixava `work-*` do pod depois que **todos** os
  4 jobs terminavam **e** um humano aprovava no Telegram — artefatos
  prontos ficavam acumulados no volume de 40GB até o fim da sessão inteira.
- Agora: `sync_finished_jobs()` roda a cada tick; assim que um job
  individual termina (`ok` ou `fail`), o `lora_adapters` já é copiado para
  `RESULTS_DIR/incremental/<pod_id>/<job_id>` no homelab, e os checkpoints
  intermediários daquele job são apagados do pod em seguida.
- Achado no caminho: o pod não tinha `rsync` instalado — o sync incremental
  falhava silenciosamente (`bash: rsync: command not found`) até
  `apt-get install rsync` no pod.

### No repositório `eddie-auto-dev` (commit `336057a1`)

`scripts/eddie_persona_finetune_peft.py` e
`scripts/whatsapp_toolcall_finetune_peft.py`:

- **Bug real de resume**: `resume_from_checkpoint` só ativava quando
  `FT_TIME_BUDGET_SECONDS` estava setado — modo usado só no treino local em
  pacotes de 10min (GPU compartilhada com Ollama de produção). No pipeline
  cloud esse orçamento é sempre `0`, então **todo treino interrompido
  reiniciava do zero** mesmo com checkpoint salvo (foi exatamente o que
  aconteceu com `eddie-persona-safe`: descartou `checkpoint-50` e
  retreinou os 100 steps inteiros). Fix: resume ativa sempre que existir
  checkpoint, independente do budget.
- `FT_SAVE_TOTAL_LIMIT` wired (antes só existia no `jobs.json`, sem nenhum
  script ler a env var).
- Documentado em `docs/variables-taxonomy/FT_FINETUNE_PIPELINE.md`.

### Governança do bot de Telegram (efeito colateral descoberto)

A aprovação do pipeline via botão do Telegram não teve efeito — investigação
achou 5 processos órfãos `telegram_mcp_server.py` (gerados via sessões SSH
não finalizadas ao longo do dia) competindo pelo mesmo token do bot com o
`telegram_bot.py` oficial, causando `409 Conflito de polling` repetidos.
Callback do botão nunca chegou a ser roteado para o `approval_gateway`.
Processos órfãos mortos, `eddie-telegram-bot.service` reiniciado, aprovação
completada via fallback documentado
(`echo approved > /var/lib/eddie/cloud_ft/approve_<session>`).

---

## Validação Pós-Correção

- `du -sh /workspace` no pod: 17GB → 16GB após hygiene + sync incremental.
- `state.json` do orquestrador: `phase=done`, `approval_status=approved`,
  4/4 jobs `ok`, 4/4 adapters baixados (740MB total).
- Benchmark automático: `train_quality=99.62`, loss `1.6793 → 0.0318`
  (melhora de 98.11%).
- `pytest tests/test_prometheus_exporter.py tests/test_grafana_dashboard_queries.py`
  — passam (não relacionado a este fix especificamente, mas parte da mesma
  sessão de trabalho no branch).

## Pendências Não Fechadas

- **Pod RunPod ainda rodando** após `done` (`CLOUD_FT_AUTO_TERMINATE=0`) —
  decisão de terminar ou não ficou em aberto com o dono.
- Deploy do `jobs.json`/`run_job.sh`/`pod_disk_hygiene.sh` canônicos foi
  feito no bundle atual do pod; bundles futuros (`prepare_bundles.sh`
  rodando de novo) já pegam a versão certa automaticamente via
  `homelab-cloud-ft` git.
- `notify_telegram` do orquestrador cloud-ft estava quebrado por
  `PYTHONPATH` faltando `/home/homelab/myClaude` (módulo
  `specialized_agents`) — corrigido via drop-in systemd
  `cloud-ft-orchestrator.service.d/pythonpath.conf`, agora versionado em
  `homelab-cloud-ft/systemd/cloud-ft-orchestrator.service.d/pythonpath.conf`.

---

## Lições Operacionais

1. **`df -h` num pod RunPod mostra o pool compartilhado, não a cota do
   volume.** Usar a API RunPod (`GET /pods/{id}` → `volumeInGb`) para saber
   o limite real.
2. **Merge fp16 no pod é caro e desnecessário** — adapters LoRA bastam para
   transporte; merge deve rodar localmente no homelab/NAS, fora da cota
   apertada do pod cloud.
3. **Nunca lançar processo longo em pod remoto sem `nohup`/`setsid`** —
   SIGHUP por queda de SSH mata o treino sem deixar rastro de causa.
4. **Commit no git não é deploy.** Um fix correto e testado pode nunca
   chegar ao host de produção se o passo de cópia via SSH falhar
   silenciosamente — vale sempre `diff` entre o que o git tem e o que está
   rodando antes de assumir que "já está corrigido".
5. **Aprovação via Telegram depende de um único poller saudável do
   token.** Processos MCP órfãos acumulados ao longo de uma sessão longa
   competem pelo `getUpdates` e derrubam callbacks de botão sem erro
   visível para quem clicou.

---

## Comandos Úteis para Diagnóstico Futuro

Ver cota real do volume do pod:

```bash
curl -s -H "Authorization: Bearer $RUNPOD_KEY" \
  "https://rest.runpod.io/v1/pods/<pod_id>" | python3 -m json.tool | grep -i volume
```

Ver estado do pipeline:

```bash
cat /var/lib/eddie/cloud_ft/state.json | python3 -m json.tool
```

Checar processos MCP órfãos do Telegram:

```bash
ps aux | grep telegram_mcp_server | grep -v grep
```

Rodar higiene de disco manual no pod:

```bash
bash /workspace/pod_disk_hygiene.sh
```
