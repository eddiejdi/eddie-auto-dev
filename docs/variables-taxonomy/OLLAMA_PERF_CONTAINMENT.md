# Ollama — Perf Containment / Concurrency (drop-in systemd)

Drop-in `zz-perf-containment.conf` do `ollama.service` (homelab, 192.168.15.2).
Snapshot versionado em `systemd/ollama.service.d/zz-perf-containment.conf`.
Contém limites de CPU/threads e a concorrência efetiva do Ollama (é o drop-in
que VENCE por ordem alfabética entre os que definem `OLLAMA_NUM_PARALLEL`).

| Variável | Default | Propósito |
|---|---|---|
| `OLLAMA_NUM_PARALLEL` | `4` | Slots de inferência paralela por modelo na GPU0 (RTX 3060 12GB; inferência ~0.4s, ~5.2GB modelo + KV cabe folgado). Ajustado 1→2→4 no incidente 503-storm 2026-07-24. Nota: acima de 2 o ganho é marginal — o resíduo de 503 é amplificação de retry (6/falha) em rajadas sincronizadas, não gargalo de capacidade. |
| `OLLAMA_MAX_QUEUE` | `32` | Fila de requisições aguardando slot antes de retornar 503. Ajustado 4→16→32 (inferência rápida drena rápido; bem abaixo do timeout de 240s). |
| `GGML_NUM_THREADS` | `4` | Threads de CPU do backend ggml (contenção de CPU do Ollama). |
| `OLLAMA_NUM_THREADS` | `4` | Threads de CPU do runtime Ollama. |
| `OMP_NUM_THREADS` | `4` | Threads OpenMP (libs numéricas). |
| `OMP_THREAD_LIMIT` | `4` | Teto rígido de threads OpenMP. |
| `MKL_NUM_THREADS` | `4` | Threads Intel MKL (distinta de `GGML_NUM_THREADS`; mesma finalidade de contenção, biblioteca diferente). |
| `OPENBLAS_NUM_THREADS` | `4` | Threads OpenBLAS. |
| `GOMAXPROCS` | `4` | Máximo de OS threads simultâneas do runtime Go do Ollama. |
