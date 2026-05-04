# secrets_agent — Correções de Concorrência (2026-05-03)

> Quatro bugs de cache/concorrência no `secrets_agent.py` causavam storm de processos `bw` que saturava o HDD do homelab.

**Arquivo:** `/home/homelab/agents_workspace/prod/tools/secrets_agent/secrets_agent.py`

---

## Contexto

O `secrets_agent` é um serviço FastAPI que encapsula o Bitwarden CLI (`bw`). Cada chamada a `bw` lê o vault (~600 KB) e escreve cache no HDD `sdd` (5400 RPM). Com 10–20 processos simultâneos o disco satura (90% util, r_await >50ms), o Squid fica lento e toda a navegação cai.

---

## Bug 1 — Cache Negativo Ausente

**Função:** `bw_get_secret_value`

**Problema:** Quando `bw_find_item_exact` retorna `None`, a função retornava sem cachear o resultado. Cada request subsequente re-executava `bw` para a mesma chave inexistente.

**Fix:**
```python
if not exact:
    with _secret_cache_lock:
        _secret_value_cache[cache_key] = (None, time.time())  # cacheia not-found
    return None
```

---

## Bug 2 — `bw_get_secret_fields` Sem Cache

**Função:** `bw_get_secret_fields`

**Problema:** A função não verificava `_secret_fields_cache` antes de executar `bw list items`. Sempre spawna `bw` independente de chamadas anteriores.

**Fix:** Adicionar verificação de cache no início da função:
```python
def bw_get_secret_fields(name: str) -> dict[str, str]:
    with _secret_cache_lock:
        if name in _secret_fields_cache:
            fields, ts = _secret_fields_cache[name]
            if time.time() - ts < BW_SECRET_TTL:
                return fields
    try:
        ...
```

---

## Bug 3 — Thundering Herd

**Função:** `bw_get_secret_value`

**Problema:** Múltiplas threads checando o cache ao mesmo tempo viam miss e todas spawnavm `bw` para a mesma chave. Especialmente grave no startup do serviço com cache vazio.

**Fix:** Dedup por chave via `threading.Event`:

Globals adicionados:
```python
_secret_inflight: dict = {}
_secret_inflight_lock = threading.Lock()
```

Lógica na função:
```python
with _secret_inflight_lock:
    if cache_key in _secret_inflight:
        ev = _secret_inflight[cache_key]
        inflight = True
    else:
        ev = threading.Event()
        _secret_inflight[cache_key] = ev
        inflight = False

if inflight:
    ev.wait(timeout=30)
    # lê cache populado pela thread líder
    with _secret_cache_lock:
        if cache_key in _secret_value_cache:
            v, ts = _secret_value_cache[cache_key]
            if time.time() - ts < BW_SECRET_TTL:
                return v
    return None

try:
    # ... fetch bw ...
finally:
    with _secret_inflight_lock:
        _secret_inflight.pop(cache_key, None)
    ev.set()
```

---

## Bug 4 — Sem Limite Global de Concorrência

**Função:** `BwManager.run_command`

**Problema:** Mesmo com dedup por chave (Bug 3), chaves *diferentes* em paralelo spawnavm muitos `bw` simultâneos sem limite.

**Fix:** `threading.Semaphore(2)` envolvendo o bloco de subprocess:

Global adicionado:
```python
_bw_subprocess_semaphore = threading.Semaphore(2)
```

Em `run_command`:
```python
with _bw_subprocess_semaphore:
    try:
        result = subprocess.run(...)
        ...
    except subprocess.TimeoutExpired:
        ...
    except FileNotFoundError:
        ...
```

---

## Diagnóstico

Para verificar se o bug voltou:
```bash
ps aux | grep '[b]w '
# Mais de 2 processos bw simultâneos = sinal de regressão
```

O `critical-services-watchdog.sh` monitora e auto-cura:
```bash
BW_COUNT=$(pgrep -c bw 2>/dev/null || echo 0)
if [ "$BW_COUNT" -gt 3 ]; then
    killall -9 bw
    systemctl restart secrets_agent
fi
```

---

## Referências

- Incidente completo: [INCIDENTS/INTERNET_OUTAGE_2026-05-03.md](INCIDENTS/INTERNET_OUTAGE_2026-05-03.md)
- Memória do projeto: `feedback_secrets_agent_thundering_herd.md`
