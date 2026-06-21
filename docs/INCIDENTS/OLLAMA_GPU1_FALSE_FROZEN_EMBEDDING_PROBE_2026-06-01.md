# Incidente — GPU1 falsa como frozen por probe incompatível com modelo de embedding — 2026-06-01

## Resumo Executivo

Em `2026-06-01` o Telegram recebeu alertas repetidos de:

- `Ollama GPU1 Frozen (GTX 1050)`
- `Ollama Selfheal Rate-Limited`

A hipótese inicial era concorrência de modelos na `GPU1`. O diagnóstico final mostrou
outra causa: o serviço `ollama-gpu-selfheal` tratava qualquer modelo ativo em
`/api/ps` como se suportasse `/api/generate`. Quando o único modelo carregado em
`GPU1` era `nomic-embed-text:latest`, o probe recebia `HTTP 400` e o script
interpretava isso como travamento.

O resultado era um falso positivo contínuo:

- `gpu1_last_ok` deixava de ser atualizado
- `ollama_gpu_frozen_seconds` crescia indefinidamente
- o self-heal tentava restart até bater `MAX_RESTARTS_HOUR=3`
- o Grafana encaminhava os alertas para o Telegram

Correção aplicada:

- o probe agora diferencia modelo generativo de modelo de embedding
- `nomic-embed-text` passa a ser validado via `/api/embeddings`
- métricas de `GPU1` voltaram a `responsive=1`, `frozen_seconds=0`, `restarts_total=0`
- não havia alertas ativos no Prometheus após o restart limpo do serviço às `2026-06-01 08:09:17 -03`

---

## Sintoma Observado

- alertas em Telegram apontando problema de "concorrência de modelos"
- logs do `ollama-gpu-selfheal` repetindo:
  - `gpu1: frozen há ...s (threshold=120s) — iniciando selfheal`
  - `gpu1: rate-limit atingido (3/3 restarts/h) — escalar manualmente`
- `ollama-gpu1.service` seguia `active (running)`, então o problema não era indisponibilidade total do serviço

Janela crítica observada no homelab:

- entre `2026-06-01 07:26 -03` e `2026-06-01 08:09 -03`
- contador de frozen chegou a ~`49k` segundos por estado stale acumulado

---

## Estado Encontrado

Validações no host `homelab (192.168.15.2)` mostraram:

### 1. Serviço vivo, mas probe errado

- `GET /api/tags` em `http://127.0.0.1:11435` respondia `200`
- `GET /api/ps` em `http://127.0.0.1:11435` respondia `200`
- modelo ativo em `GPU1`: `nomic-embed-text:latest`

### 2. O modelo carregado era de embedding, não de geração

Teste reproduzido:

```bash
curl -sS --max-time 10 \
  -H 'Content-Type: application/json' \
  -d '{"model":"nomic-embed-text:latest","prompt":"ping","stream":false,"options":{"num_predict":1}}' \
  http://127.0.0.1:11435/api/generate
```

Resposta:

```json
{"error":"\"nomic-embed-text:latest\" does not support generate"}
```

Teste compatível:

```bash
curl -sS --max-time 10 \
  -H 'Content-Type: application/json' \
  -d '{"model":"nomic-embed-text:latest","prompt":"ping"}' \
  http://127.0.0.1:11435/api/embeddings
```

Resultado esperado:

- JSON com chave `embedding`

### 3. O self-heal antigo não distinguia o tipo do modelo

Antes da correção, o fluxo lógico em `monitoring/ollama_gpu_selfheal.sh` era:

1. descobrir o primeiro modelo ativo via `/api/ps`
2. chamar sempre `probe_generate()`
3. considerar falha no probe como falta de responsividade

Isso funciona para `qwen*`, `phi*`, `trading-analyst` etc., mas falha para
modelos `embeddings-only`.

---

## Causa Raiz

### Causa 1 — probe sem noção de capacidade do modelo

O script `monitoring/ollama_gpu_selfheal.sh` usava apenas o nome do modelo
ativo. Não avaliava se o modelo era:

- generativo (`/api/generate`)
- embeddings-only (`/api/embeddings`)

Com `nomic-embed-text:latest` carregado e saudável, o probe incorreto retornava
`400`, gerando falso frozen.

### Causa 2 — estado stale no diretório de self-heal

Como o probe falhava em todo ciclo:

- `STATE_DIR/gpu1_last_ok` não era atualizado
- `frozen_secs` só crescia
- o restart rate-limitado persistia até intervenção manual

### Causa 3 — drift no template local de alerta

O template versionado `monitoring/grafana_gpu_alert_rules.yml` ainda usava:

```promql
max(ollama_gpu_selfheal_restarts_total) >= 3
```

Já o arquivo provisionado ativo no stack Grafana usava:

```promql
max(increase(ollama_gpu_selfheal_restarts_total[1h])) >= 3
```

Esse drift não foi a causa do falso frozen, mas deixava o template local
desalinhado do comportamento real de produção.

---

## Correções Aplicadas

### Repositório

Arquivos alterados:

- `monitoring/ollama_gpu_selfheal.sh`
- `monitoring/grafana_gpu_alert_rules.yml`
- `tests/test_ollama_gpu_selfheal_script.py`

#### `monitoring/ollama_gpu_selfheal.sh`

Mudanças principais:

- novo `probe_embeddings()` para modelos `embeddings-only`
- novo `active_model_info()` para capturar:
  - `name`
  - `details.family`
  - `details.families`
- novo `model_probe_kind()` para decidir entre:
  - `generate`
  - `embeddings`
- novo `probe_model()` para aplicar o probe correto
- comentários de métrica ajustados para refletir probe de modelo ativo, não só generate
- `STATE_DIR`, `TEXTFILE_DIR`, `PROM_FILE` e `TMP_FILE` passaram a aceitar override por ambiente
- entrypoint encapsulado em:

```bash
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
```

Isso permite `source` do script em testes sem disparar o loop infinito.

#### `tests/test_ollama_gpu_selfheal_script.py`

Cobertura adicionada:

- modelo de embedding usa `/api/embeddings`
- modelo generativo usa `/api/generate`
- sintaxe bash do script continua válida

#### `monitoring/grafana_gpu_alert_rules.yml`

Alinhado com o arquivo provisionado real:

```promql
max(increase(ollama_gpu_selfheal_restarts_total[1h])) >= 3
```

### Produção no homelab

Passos executados:

1. deploy do script via:

```bash
bash monitoring/deploy_gpu_selfheal.sh
```

2. confirmação de que o arquivo novo estava no host:

```bash
grep -n 'probe_embeddings\|model_probe_kind' /usr/local/bin/ollama_gpu_selfheal
```

3. restart limpo do serviço, porque `enable --now` não substitui o processo bash
   já em execução:

```bash
sudo systemctl stop ollama-gpu-selfheal
```

4. reset do estado falso da `GPU1`:

```bash
now=$(date +%s)
printf "%s\n" "$now" | sudo tee /var/lib/ollama-selfheal/gpu1_last_ok >/dev/null
printf "0\n" | sudo tee /var/lib/ollama-selfheal/gpu1_restarts >/dev/null
printf "0\n" | sudo tee /var/lib/ollama-selfheal/gpu1_restart_ts >/dev/null
```

5. subida do serviço com código novo:

```bash
sudo systemctl start ollama-gpu-selfheal
```

---

## Validação Pós-Correção

### Validação local do script no repositório

Executado com sucesso:

```bash
pytest -q tests/test_ollama_gpu_selfheal_script.py
bash -n monitoring/ollama_gpu_selfheal.sh
```

### Validação funcional no host

Comando:

```bash
sudo /usr/local/bin/ollama_gpu_selfheal --once
```

Resultado relevante observado:

- `ollama_gpu_up{gpu="gpu1",model="nomic-embed-text:latest"} 1`
- `ollama_gpu_responsive{gpu="gpu1",model="nomic-embed-text:latest"} 1`
- `ollama_gpu_frozen_seconds{gpu="gpu1",model="nomic-embed-text:latest"} 0`
- `ollama_gpu_selfheal_restarts_total{gpu="gpu1",model="nomic-embed-text:latest"} 0`

### Estado do serviço após o restart limpo

Validação:

```bash
systemctl status ollama-gpu-selfheal --no-pager -l
```

Estado confirmado:

- `active (running)`
- reiniciado em `2026-06-01 08:09:17 -03`

### Estado dos alertas

Validação:

```bash
curl -sf http://127.0.0.1:9090/api/v1/alerts
```

Resultado:

- `alerts: []`

---

## Interpretação Correta do Incidente

O problema percebido como "concorrência de modelos" era, neste caso, um efeito
secundário do alerting:

- havia um único modelo ativo em `GPU1`
- esse modelo era saudável
- o self-heal só estava usando o endpoint errado para testá-lo

Portanto:

- não era disputa real entre dois modelos generativos
- não era indisponibilidade do `ollama-gpu1.service`
- não era falha do Telegram

Era um falso positivo do health check.

---

## Lições Operacionais

1. **Modelo ativo não implica `/api/generate` válido**.
   `nomic-embed-text` precisa ser validado via `/api/embeddings`.

2. **Alerta de frozen precisa ser correlacionado com `/api/ps` antes de inferir concorrência real**.
   O primeiro passo deve ser identificar qual modelo está carregado.

3. **Deploy de script em serviço bash precisa de restart real**.
   Copiar o arquivo e rodar `enable --now` não atualiza um processo já em memória.

4. **Métricas rate-limited devem usar janela temporal explícita**.
   O template local deve continuar alinhado com a regra provisionada.

5. **`GPU1` pode operar corretamente apenas com modelo de embedding carregado**.
   Isso é estado válido, não sintoma de falha.

---

## Comandos Úteis para Diagnóstico Futuro

Ver modelo ativo:

```bash
curl -sS http://127.0.0.1:11435/api/ps
```

Ver catálogo:

```bash
curl -sS http://127.0.0.1:11435/api/tags
```

Testar embedding:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"model":"nomic-embed-text:latest","prompt":"ping"}' \
  http://127.0.0.1:11435/api/embeddings
```

Forçar uma rodada do self-heal:

```bash
sudo /usr/local/bin/ollama_gpu_selfheal --once
```

Ver últimas entradas do serviço:

```bash
journalctl -u ollama-gpu-selfheal -n 50 --no-pager
```

Ver métricas exportadas:

```bash
grep -v '^#' /var/lib/prometheus/node-exporter/ollama_gpu.prom
```
